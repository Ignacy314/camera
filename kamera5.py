import sys
import xml.etree.ElementTree as ET  # Do budowania XML, jeśli zajdzie potrzeba bardziej złożonej struktury

import requests
from requests.auth import HTTPDigestAuth

# --- Konfiguracja Kamery ---
CAMERA_IP = "192.168.1.64"
# Standardowy port HTTP, zazwyczaj 80
CAMERA_PORT = 80
CAMERA_USER = "admin"
# Zmień na hasło Twojej kamery - MUSI BYĆ POPRAWNE!
CAMERA_PASS = "1plus2jest3"  # <-- WAŻNE: Wprowadź tutaj swoje PRAWDZIWE hasło!

# --- Punkt końcowy ISAPI dla absolutnego PTZ ---
# Może się różnić w zależności od modelu/firmware. Sprawdź dokumentację ISAPI dla swojej kamery.
# /channels/1/ odnosi się do pierwszego kanału wideo.
ISAPI_ENDPOINT = f"http://{CAMERA_IP}:{CAMERA_PORT}/ISAPI/PTZCtrl/channels/1/absolute"


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


def construct_ptz_xml(pan_degrees, tilt_degrees, zoom_level):
    """
    Konstruuje payload XML dla komendy AbsoluteHigh ISAPI.
    UWAGA: Skalowanie wartości (mnożenie przez 10) i nazwy tagów
          mogą wymagać dostosowania do konkretnego modelu kamery!
    """
    # Przykładowe skalowanie: stopnie * 10, zoom * 10
    # Sprawdź dokumentację ISAPI swojej kamery dla dokładnych wymagań.
    elevation_val = int(tilt_degrees * 10)
    azimuth_val = int(pan_degrees * 10)
    zoom_val = int(zoom_level * 10)

    # Prosty sposób budowania XML jako string
    xml_payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<PTZData>
    <AbsoluteHigh>
        <elevation>{elevation_val}</elevation>
        <azimuth>{azimuth_val}</azimuth>
        <absoluteZoom>{zoom_val}</absoluteZoom>
    </AbsoluteHigh>
</PTZData>
"""
    # Alternatywnie, używając xml.etree.ElementTree dla bardziej złożonych struktur:
    # root = ET.Element("PTZData")
    # abs_high = ET.SubElement(root, "AbsoluteHigh")
    # ET.SubElement(abs_high, "elevation").text = str(elevation_val)
    # ET.SubElement(abs_high, "azimuth").text = str(azimuth_val)
    # ET.SubElement(abs_high, "absoluteZoom").text = str(zoom_val)
    # xml_payload = ET.tostring(root, encoding='unicode')

    return xml_payload


# --- Główna logika ---
def main():
    """Główna funkcja programu."""
    print("--- Sterowanie kamerą Hikvision przez ISAPI ---")

    # Uwierzytelnianie HTTP Digest
    auth = HTTPDigestAuth(CAMERA_USER, CAMERA_PASS)

    # Pobranie danych od użytkownika
    # Zakresy mogą wymagać dostosowania do specyfikacji kamery DS-2DE4425IW-DE
    # Pan: 0-360 stopni, Tilt: zwykle 0-90 lub -90 do +90, Zoom: 1x do 25x dla tego modelu
    print("\nPodaj docelowe wartości:")
    pan_val = get_float_input("  Kąt poziomy (Pan) [0.0 - 360.0 stopni]: ", 0.0, 360.0)
    # Dostosuj zakres Tilt, jeśli jest inny (np. -90 do 90)
    tilt_val = get_float_input("  Kąt pionowy (Tilt) [0.0 - 90.0 stopni]: ", 0.0, 90.0)
    zoom_val = get_float_input(
        "  Poziom przybliżenia (Zoom) [1.0 - 25.0 x]: ", 1.0, 25.0
    )

    # Konstrukcja payloadu XML
    xml_data = construct_ptz_xml(pan_val, tilt_val, zoom_val)
    print("\nPrzygotowany XML:")
    print(xml_data)

    # Nagłówki HTTP
    headers = {"Content-Type": "application/xml"}

    # Wysłanie żądania PUT
    print(f"Wysyłanie żądania PUT do: {ISAPI_ENDPOINT}")
    try:
        response = requests.put(
            ISAPI_ENDPOINT, headers=headers, data=xml_data, auth=auth, timeout=10
        )  # Timeout 10 sekund

        # Sprawdzenie odpowiedzi
        print(f"Status odpowiedzi HTTP: {response.status_code}")
        print("Odpowiedź serwera (tekst):")
        print(response.text)  # Wyświetl odpowiedź tekstową z kamery

        if response.status_code == 200:
            print("\nKomenda PTZ wysłana pomyślnie przez ISAPI!")
        else:
            print("\nWystąpił błąd podczas wysyłania komendy ISAPI.")
            if response.status_code == 401:
                print(
                    ">>> Błąd 401 Unauthorized: Sprawdź poprawność nazwy użytkownika i hasła (CAMERA_USER, CAMERA_PASS)."
                )
            elif response.status_code == 404:
                print(
                    f">>> Błąd 404 Not Found: Sprawdź poprawność adresu URL ISAPI ({ISAPI_ENDPOINT})."
                )
            elif response.status_code == 403:
                print(
                    ">>> Błąd 403 Forbidden: Użytkownik może nie mieć uprawnień do sterowania PTZ przez ISAPI."
                )
            # Można dodać obsługę innych kodów błędów (np. 500 Internal Server Error)

    except requests.exceptions.ConnectionError as e:
        print(f"\nBłąd połączenia: Nie można połączyć się z {CAMERA_IP}:{CAMERA_PORT}.")
        print(
            ">>> Sprawdź adres IP, port, połączenie sieciowe i czy kamera jest włączona."
        )
        # print(f">>> Szczegóły błędu: {e}")
    except requests.exceptions.Timeout:
        print("\nBłąd: Przekroczono czas oczekiwania na odpowiedź od kamery.")
    except requests.exceptions.RequestException as e:
        print(f"\nWystąpił błąd biblioteki requests: {e}")
    except Exception as e:
        print(f"\nWystąpił nieoczekiwany błąd: {e}")
        # traceback.print_exc() # Odkomentuj dla pełnego śledzenia błędu
    finally:
        print("\nZakończono działanie skryptu.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nPrzerwano przez użytkownika.")
