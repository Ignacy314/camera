import asyncio
import os
import sys
import traceback  # Dodano do śledzenia błędów

from onvif import ONVIFCamera
from zeep.exceptions import Fault

# --- Konfiguracja Kamery ---
# Zmień na adres IP Twojej kamery
CAMERA_IP = "192.168.3.64"
# Standardowy port ONVIF, może być inny (np. 8000) - SPRAWDŹ W KAMERZE!
CAMERA_PORT = 80
# Zmień na nazwę użytkownika Twojej kamery
CAMERA_USER = "admin"
# Zmień na hasło Twojej kamery - MUSI BYĆ POPRAWNE!
CAMERA_PASS = "1plus2jest3"  # <-- WAŻNE: Wprowadź tutaj swoje PRAWDZIWE hasło!

# --- Ścieżka WSDL ---
# Ustawiamy na None, aby biblioteka użyła domyślnego mechanizmu
WSDL_PATH = None
print(
    f"Ścieżka WSDL ustawiona na: {WSDL_PATH} (użycie mechanizmu domyślnego biblioteki)"
)
# --- Koniec sekcji WSDL ---


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
        # Użyj tokenu pierwszego profilu
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
        # Utworzenie obiektu kamery, przekazując None jako ścieżkę WSDL
        print(
            f"Próba utworzenia obiektu ONVIFCamera dla {CAMERA_IP}:{CAMERA_PORT} (WSDL_PATH=None)"
        )
        mycam = ONVIFCamera(
            CAMERA_IP, CAMERA_PORT, CAMERA_USER, CAMERA_PASS, WSDL_PATH
        )  # WSDL_PATH jest teraz None
        print(f"Obiekt ONVIFCamera utworzony.")

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
        if "NotAuthorized" in str(e) or "forbidden" in str(e).lower():
            print(">>> BŁĄD KRYTYCZNY: Błąd autoryzacji (NotAuthorized/Forbidden).")
            print(">>> UPEWNIJ SIĘ, że HASŁO (CAMERA_PASS) w skrypcie jest POPRAWNE!")
            print(
                ">>> Sprawdź też, czy użytkownik (CAMERA_USER) ma uprawnienia ONVIF w kamerze."
            )
        elif "Connection Error" in str(e) or "Timeout" in str(e):
            print(
                ">>> Błąd połączenia ONVIF. Sprawdź adres IP, port i dostępność kamery w sieci."
            )
        else:
            print(f">>> Inny błąd ONVIF: {e}")
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
                f">>> 1. SPRAWDŹ HASŁO! Czy na pewno wpisałeś POPRAWNE hasło w zmiennej CAMERA_PASS?"
            )
            print(
                f">>> 2. SPRAWDŹ PORT! Czy port ONVIF w kamerze to na pewno {CAMERA_PORT}? Często jest to 80, ale może być inny (np. 8000). Sprawdź w ustawieniach sieciowych kamery."
            )
            print(
                f">>> 3. SPRAWDŹ USTAWIENIA ONVIF W KAMERZE! Czy protokół ONVIF jest włączony? Czy użytkownik '{CAMERA_USER}' ma nadane uprawnienia do ONVIF (czasem trzeba go dodać osobno)?"
            )
            print(
                f">>> 4. SPRAWDŹ SIEĆ! Czy na pewno Raspberry Pi widzi kamerę (ping {CAMERA_IP})? Czy nie ma firewalla?"
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
