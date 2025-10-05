import asyncio
import os
import sys
import traceback  # Dodano do śledzenia błędów

from onvif import ONVIFCamera
from zeep.exceptions import Fault

# --- Konfiguracja Kamery ---
# Zmień na adres IP Twojej kamery
CAMERA_IP = "192.168.3.64"
# Standardowy port ONVIF, może być inny (np. 8000)
CAMERA_PORT = 80
# Zmień na nazwę użytkownika Twojej kamery
CAMERA_USER = "user"
# Zmień na hasło Twojej kamery
CAMERA_PASS = "1plus2jest3"  # <-- WAŻNE: Wprowadź tutaj swoje hasło!

WSDL_PATH = "/home/test/python-onvif-zeep/wsdl"


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
        print("Pobieranie serwisu PTZ...")
        ptz_service = await camera.create_ptz_service()
        if ptz_service is None:
            print("Błąd: Nie udało się utworzyć serwisu PTZ (zwrócono None).")
            return
        print("Pobrano serwis PTZ.")

        # Pobranie dostępnych profili mediów (zazwyczaj pierwszy jest głównym)
        print("Pobieranie profili mediów...")
        profiles = await camera.get_media_profiles()
        if not profiles:
            print("Nie znaleziono profili mediów.")
            return
        profile_token = profiles[0].token
        print(f"Używany token profilu: {profile_token}")

        # Przygotowanie parametrów ruchu
        move_request = ptz_service.create_type("AbsoluteMove")
        move_request.ProfileToken = profile_token
        move_request.Position = {"PanTilt": {"x": pan, "y": tilt}, "Zoom": {"x": zoom}}

        print(f"Wysyłanie komendy AbsoluteMove: Pan={pan}, Tilt={tilt}, Zoom={zoom}")
        await ptz_service.AbsoluteMove(move_request)
        print("Komenda AbsoluteMove wysłana pomyślnie.")

    except Fault as e:
        print(f"Błąd ONVIF podczas próby ruchu: {e}")
    except Exception as e:
        print(f"Niespodziewany błąd podczas ruchu kamery: {e}")
        # traceback.print_exc() # Odkomentuj dla pełnego śledzenia błędu


async def main():
    """Główna funkcja programu."""
    print("Inicjalizacja obiektu kamery...")
    mycam = None  # Inicjalizacja na None
    try:
        # Utworzenie obiektu kamery
        mycam = ONVIFCamera(CAMERA_IP, CAMERA_PORT, CAMERA_USER, CAMERA_PASS, WSDL_PATH)
        print(f"Obiekt ONVIFCamera utworzony dla {CAMERA_IP}:{CAMERA_PORT}.")

        # Sprawdzenie, czy metoda update_xaddrs istnieje (sanity check)
        if not hasattr(mycam, "update_xaddrs") or not callable(mycam.update_xaddrs):
            print(
                "Błąd krytyczny: Obiekt kamery nie ma metody 'update_xaddrs'. Problem z biblioteką?"
            )
            return

        # Próba połączenia i aktualizacji adresów usług
        print("Łączenie z kamerą i aktualizacja adresów usług (await update_xaddrs)...")
        await mycam.update_xaddrs()  # Pobierz aktualne adresy usług
        print("Pomyślnie połączono z kamerą i zaktualizowano adresy usług.")

        # Pobranie danych od użytkownika (wartości znormalizowane)
        print("\nPodaj docelowe wartości (zakresy dla wartości znormalizowanych):")
        pan_val = get_float_input("  Kąt poziomy (Pan) [-1.0 do 1.0]: ", -1.0, 1.0)
        tilt_val = get_float_input("  Kąt pionowy (Tilt) [-1.0 do 1.0]: ", -1.0, 1.0)
        zoom_val = get_float_input(
            "  Poziom przybliżenia (Zoom) [0.0 do 1.0]: ", 0.0, 1.0
        )

        # Wykonanie ruchu
        await move_camera(mycam, pan_val, tilt_val, zoom_val)

    # --- Obsługa błędów ---
    except Fault as e:
        print(f"Błąd ONVIF: {e}")
        if "NotAuthorized" in str(e):
            print(">>> Błąd autoryzacji. Sprawdź nazwę użytkownika i hasło w skrypcie.")
        elif "Connection Error" in str(e) or "Timeout" in str(e):
            print(
                ">>> Błąd połączenia ONVIF. Sprawdź adres IP, port i dostępność kamery w sieci."
            )
        else:
            # traceback.print_exc() # Odkomentuj dla pełnego śledzenia błędu
            pass
    except ConnectionRefusedError:
        print(
            f">>> Nie można nawiązać połączenia TCP z kamerą pod adresem {CAMERA_IP}:{CAMERA_PORT}."
        )
        print(
            ">>> Sprawdź, czy adres IP i port są poprawne, czy kamera jest włączona i czy nie ma blokady firewall."
        )
    except TypeError as e:
        if "object NoneType can't be used in 'await' expression" in str(e):
            print(f"Wystąpił błąd TypeError podczas 'await': {e}")
            print(
                ">>> Możliwa przyczyna: Problem z inicjalizacją połączenia ONVIF na wczesnym etapie."
            )
            print(
                f">>> Sprawdź poprawność danych konfiguracyjnych (IP: {CAMERA_IP}, Port: {CAMERA_PORT}, User: {CAMERA_USER}, Pass: {'*' * len(CAMERA_PASS) if CAMERA_PASS else 'Brak'}), działanie kamery oraz ustawienia ONVIF w kamerze."
            )
            print(
                f">>> Sprawdź, czy ścieżka WSDL ({WSDL_PATH}) jest poprawna lub czy biblioteka może ją znaleźć."
            )
            # traceback.print_exc() # Odkomentuj dla pełnego śledzenia błędu
        else:
            print(f"Wystąpił nieoczekiwany błąd TypeError: {e}")
            # traceback.print_exc() # Odkomentuj dla pełnego śledzenia błędu
    except Exception as e:
        # Złap inne nieoczekiwane błędy
        print(f"Wystąpił nieoczekiwany błąd ogólny: {e}")
        # traceback.print_exc() # Odkomentuj dla pełnego śledzenia błędu
    finally:
        # Zawsze próbuj zamknąć połączenie, chociaż w onvif-zeep nie ma jawnej metody close()
        # Biblioteka zarządza połączeniami automatycznie.
        print("Zakończono działanie skryptu.")


if __name__ == "__main__":
    # Uruchomienie pętli zdarzeń asyncio
    try:
        # W systemie Windows może być potrzebna inna polityka pętli zdarzeń
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPrzerwano przez użytkownika.")
