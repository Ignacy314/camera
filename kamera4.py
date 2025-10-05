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
# Używamy ścieżki, która według użytkownika działała.
# Możesz ją zmienić, jeśli jest inna.
USER_PROVIDED_WSDL_PATH = "/home/test/python-onvif-zeep/wsdl"
WSDL_PATH = USER_PROVIDED_WSDL_PATH  # Domyślnie użyj ścieżki użytkownika

# Opcjonalna próba automatycznego wykrywania (można odkomentować, jeśli chcesz)
# try:
#     import onvif
#     auto_wsdl_dir = os.path.join(os.path.dirname(onvif.__file__), 'wsdl')
#     if os.path.isdir(auto_wsdl_dir):
#         WSDL_PATH = auto_wsdl_dir
#         print(f"Automatycznie wykryto ścieżkę WSDL: {WSDL_PATH}")
#     elif os.path.isdir(USER_PROVIDED_WSDL_PATH):
#          WSDL_PATH = USER_PROVIDED_WSDL_PATH
#          print(f"Automatyczne wykrywanie nie powiodło się. Używam ścieżki podanej: {WSDL_PATH}")
#     else:
#          print(f"OSTRZEŻENIE: Nie znaleziono WSDL ani automatycznie, ani pod ścieżką {USER_PROVIDED_WSDL_PATH}.")
#          # Skrypt prawdopodobnie zawiedzie przy tworzeniu ONVIFCamera
# except Exception as e:
#     print(f"Błąd podczas automatycznego szukania WSDL: {e}. Używam ścieżki podanej: {USER_PROVIDED_WSDL_PATH}")
#     WSDL_PATH = USER_PROVIDED_WSDL_PATH

print(f"Używana ścieżka WSDL: {WSDL_PATH}")
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
        # --- WAŻNE: Sprawdzenie ścieżki WSDL przed użyciem ---
        if (
            not WSDL_PATH
            or not isinstance(WSDL_PATH, str)
            or not os.path.isdir(WSDL_PATH)
        ):
            print(
                f"BŁĄD KRYTYCZNY: Ścieżka WSDL ('{WSDL_PATH}') jest nieprawidłowa, nie istnieje lub nie jest katalogiem."
            )
            print(">>> Popraw zmienną USER_PROVIDED_WSDL_PATH na górze skryptu.")
            return  # Zakończ, jeśli ścieżka jest zła
        # --- Koniec sprawdzania WSDL ---

        # Utworzenie obiektu kamery
        print(
            f"Próba utworzenia obiektu ONVIFCamera dla {CAMERA_IP}:{CAMERA_PORT} używając WSDL: {WSDL_PATH}"
        )
        mycam = ONVIFCamera(CAMERA_IP, CAMERA_PORT, CAMERA_USER, CAMERA_PASS, WSDL_PATH)
        print(f"Obiekt ONVIFCamera utworzony.")

        # Sprawdzenie, czy metoda update_xaddrs istnieje (sanity check)
        if not hasattr(mycam, "update_xaddrs") or not callable(mycam.update_xaddrs):
            print(
                "Błąd krytyczny: Obiekt kamery nie ma metody 'update_xaddrs'. Problem z biblioteką?"
            )
            return

        # Próba połączenia i aktualizacji adresów usług
        print("Łączenie z kamerą i aktualizacja adresów usług (await update_xaddrs)...")
        await mycam.update_xaddrs()  # Pobierz aktualne adresy usług <--- TUTAJ WYSTĘPOWAŁ PIERWOTNY BŁĄD
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
        # Sprawdzanie błędów autoryzacji jest kluczowe
        if (
            "NotAuthorized" in str(e)
            or "forbidden" in str(e).lower()
            or "auth" in str(e).lower()
        ):
            print(
                ">>> BŁĄD KRYTYCZNY: Błąd autoryzacji (NotAuthorized/Forbidden/Auth error)."
            )
            print(">>> UPEWNIJ SIĘ, że HASŁO (CAMERA_PASS) w skrypcie jest POPRAWNE!")
            print(
                ">>> Sprawdź też, czy użytkownik (CAMERA_USER) ma WŁĄCZONE uprawnienia ONVIF i PTZ w ustawieniach kamery."
            )
        elif (
            "Connection Error" in str(e)
            or "Timeout" in str(e)
            or "cannot connect" in str(e).lower()
        ):
            print(
                f">>> Błąd połączenia ONVIF. Sprawdź adres IP ({CAMERA_IP}), port ({CAMERA_PORT}) i dostępność kamery w sieci."
            )
            print(
                f">>> Upewnij się, że port ONVIF w kamerze to na pewno {CAMERA_PORT} (może być np. 8000)."
            )
        else:
            print(f">>> Inny błąd ONVIF: {e}")
            traceback.print_exc()  # Drukuj ślad dla innych błędów ONVIF
    except ConnectionRefusedError:
        print(
            f">>> Nie można nawiązać połączenia TCP z kamerą pod adresem {CAMERA_IP}:{CAMERA_PORT}."
        )
        print(
            ">>> Sprawdź, czy adres IP i port są poprawne, czy kamera jest włączona i czy nie ma blokady firewall."
        )
    except TypeError as e:
        # Ten błąd może wrócić, jeśli problem leży w komunikacji/autoryzacji
        if "object NoneType can't be used in 'await' expression" in str(e):
            print(f"Wystąpił błąd TypeError podczas 'await update_xaddrs': {e}")
            print(
                ">>> TEN BŁĄD NAJPRAWDOPODOBNIEJ OZNACZA PROBLEM Z POŁĄCZENIEM/AUTORYZACJĄ MIMO POPRAWNEJ ŚCIEŻKI WSDL!"
            )
            print(
                f">>> 1. SPRAWDŹ HASŁO! Czy na pewno wpisałeś POPRAWNE hasło dla użytkownika '{CAMERA_USER}' w zmiennej CAMERA_PASS?"
            )
            print(
                f">>> 2. SPRAWDŹ PORT! Czy port ONVIF w kamerze to na pewno {CAMERA_PORT}? Sprawdź w ustawieniach sieciowych kamery (często 80 lub 8000)."
            )
            print(
                f">>> 3. SPRAWDŹ USTAWIENIA ONVIF W KAMERZE! Czy protokół ONVIF jest WŁĄCZONY? Czy użytkownik '{CAMERA_USER}' jest dodany do listy użytkowników ONVIF i ma uprawnienia 'Kontrola PTZ'?"
            )
            print(
                f">>> 4. SPRAWDŹ SIEĆ! Czy Raspberry Pi widzi kamerę (ping {CAMERA_IP})? Czy nie ma firewalla?"
            )
            traceback.print_exc()  # Drukuj pełny ślad dla tego błędu
        else:
            print(f"Wystąpił nieoczekiwany błąd TypeError: {e}")
            traceback.print_exc()
    except Exception as e:
        # Złap inne nieoczekiwane błędy
        print(f"Wystąpił nieoczekiwany błąd ogólny: {e}")
        traceback.print_exc()
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
