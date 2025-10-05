import asyncio
from onvif import ONVIFCamera
from zeep.exceptions import Fault
import sys
import os

# --- Konfiguracja Kamery ---
# Zmień na adres IP Twojej kamery
CAMERA_IP = '192.168.3.64'
# Standardowy port ONVIF, może być inny (np. 8000)
CAMERA_PORT = 80
# Zmień na nazwę użytkownika Twojej kamery
CAMERA_USER = 'admin'
# Zmień na hasło Twojej kamery
CAMERA_PASS = 'TwojeHaslo' # <-- WAŻNE: Wprowadź tutaj swoje hasło!
# Ścieżka do plików WSDL (zazwyczaj biblioteka znajduje je automatycznie)
# Jeśli wystąpią problemy, odkomentuj i podaj poprawną ścieżkę:
# WSDL_PATH = '/path/to/onvif_zeep/wsdl/'
WSDL_PATH = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), 'Lib', 'site-packages', 'wsdl') if hasattr(sys, 'executable') else os.path.join(os.path.dirname(__file__), 'wsdl')


# --- Funkcje pomocnicze ---
def get_float_input(prompt, min_val, max_val):
    """Pobiera od użytkownika wartość zmiennoprzecinkową w zadanym zakresie."""
    while True:
        try:
            value_str = input(prompt)
            value = float(value_str)
            if min_val <= value <= max_val:
                return value
            else:
                print(f"Wartość musi być pomiędzy {min_val} a {max_val}.")
        except ValueError:
            print("Nieprawidłowa wartość. Proszę podać liczbę.")
        except EOFError:
            print("\nAnulowano wprowadzanie.")
            sys.exit(0)


async def move_camera(camera, pan, tilt, zoom):
    """Wysyła komendę ruchu absolutnego do kamery."""
    try:
        # Pobranie serwisu PTZ
        ptz_service = await camera.create_ptz_service()
        print("Pobrano serwis PTZ.")

        # Pobranie dostępnych profili mediów (zazwyczaj pierwszy jest głównym)
        profiles = await camera.get_media_profiles()
        if not profiles:
            print("Nie znaleziono profili mediów.")
            return
        profile_token = profiles[0].token
        print(f"Używany token profilu: {profile_token}")

        # Przygotowanie parametrów ruchu
        # ONVIF AbsoluteMove używa znormalizowanych wartości:
        # Pan: -1.0 (lewo) do 1.0 (prawo)
        # Tilt: -1.0 (dół) do 1.0 (góra)
        # Zoom: 0.0 (szeroko) do 1.0 (wąsko/maksymalne przybliżenie)
        # UWAGA: Mapowanie stopni/poziomu zoomu na wartości znormalizowane
        # może wymagać kalibracji lub znajomości specyfikacji kamery.
        # Ten skrypt przyjmuje bezpośrednio wartości znormalizowane.
        move_request = ptz_service.create_type('AbsoluteMove')
        move_request.ProfileToken = profile_token
        move_request.Position = {'PanTilt': {'x': pan, 'y': tilt}, 'Zoom': {'x': zoom}}
        # Opcjonalnie można ustawić prędkość (również znormalizowaną)
        # move_request.Speed = {'PanTilt': {'x': 0.5, 'y': 0.5}, 'Zoom': {'x': 0.5}}

        print(f"Wysyłanie komendy AbsoluteMove: Pan={pan}, Tilt={tilt}, Zoom={zoom}")
        await ptz_service.AbsoluteMove(move_request)
        print("Komenda AbsoluteMove wysłana pomyślnie.")

        # Krótka pauza, aby kamera zdążyła zareagować (opcjonalnie)
        # await asyncio.sleep(1)
        # print("Kamera powinna być w nowej pozycji.")

    except Fault as e:
        print(f"Błąd ONVIF podczas próby ruchu: {e}")
    except Exception as e:
        print(f"Niespodziewany błąd podczas ruchu kamery: {e}")


async def main():
    """Główna funkcja programu."""
    print("Łączenie z kamerą...")
    mycam = ONVIFCamera(CAMERA_IP, CAMERA_PORT, CAMERA_USER, CAMERA_PASS, WSDL_PATH)

    try:
        await mycam.update_xaddrs() # Pobierz aktualne adresy usług
        print("Pomyślnie połączono z kamerą i zaktualizowano adresy usług.")

        # Pobranie danych od użytkownika (wartości znormalizowane)
        print("\nPodaj docelowe wartości (zakresy dla wartości znormalizowanych):")
        pan_val = get_float_input("  Kąt poziomy (Pan) [-1.0 do 1.0]: ", -1.0, 1.0)
        tilt_val = get_float_input("  Kąt pionowy (Tilt) [-1.0 do 1.0]: ", -1.0, 1.0)
        zoom_val = get_float_input("  Poziom przybliżenia (Zoom) [0.0 do 1.0]: ", 0.0, 1.0)

        # Wykonanie ruchu
        await move_camera(mycam, pan_val, tilt_val, zoom_val)

    except Fault as e:
        print(f"Błąd ONVIF: {e}")
        if "NotAuthorized" in str(e):
            print("Błąd autoryzacji. Sprawdź nazwę użytkownika i hasło.")
        elif "Connection Error" in str(e) or "Timeout" in str(e):
             print("Błąd połączenia. Sprawdź adres IP, port i dostępność kamery w sieci.")
    except ConnectionRefusedError:
        print(f"Nie można połączyć się z kamerą pod adresem {CAMERA_IP}:{CAMERA_PORT}. Sprawdź adres IP, port i czy kamera jest włączona.")
    except Exception as e:
        print(f"Wystąpił nieoczekiwany błąd: {e}")
    finally:
        # Zawsze próbuj zamknąć połączenie, chociaż w onvif-zeep nie ma jawnej metody close()
        # Biblioteka zarządza połączeniami automatycznie.
        print("Zakończono działanie skryptu.")


if __name__ == '__main__':
    # Uruchomienie pętli zdarzeń asyncio
    try:
        # W systemie Windows może być potrzebna inna polityka pętli zdarzeń
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPrzerwano przez użytkownika.")
