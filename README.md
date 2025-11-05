# System Zarządzania Stacjami EV

Prototyp systemu do monitorowania i zarządzania stacjami ładowania EV z autentykacją, zdalnym sterowaniem i symulacją stacji.

## Technologie

*   **Backend:** Python (FastAPI, SQLAlchemy, SQLite, PyJWT, Passlib)
*   **Frontend:** React (create-react-app, axios)
*   **Komunikacja:** WebSockets

## Struktura Projektu

*   `backend.py`: Główny plik backendu FastAPI z autentykacją i logiką sesji.
*   `station_simulator.py`: Skrypt symulujący stację EV z interakcją.
*   `requirements.txt`: Zależności Pythona.
*   `frontend/`: Folder z kodem React.

## Uruchomienie

1.  Sklonuj repozytorium.
2.  Przejdź do katalogu projektu.
3.  Utwórz i aktywuj wirtualne środowisko Pythona:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/macOS
    # venv\Scripts\activate # Windows
    ```
4.  Zainstaluj zależności backendu:
    ```bash
    pip install -r requirements.txt
    ```
5.  Uruchom backend:
    ```bash
    python backend.py
    ```
    Domyślnie uruchamia się na `http://localhost:8000`. Domyślny użytkownik: `admin`, hasło: `admin123`.
6.  W nowym terminalu, przejdź do folderu `frontend` i uruchom frontend:
    ```bash
    cd frontend
    npm install
    npm start
    ```
    Frontend uruchamia się na `http://localhost:3000`.
7.  W trzecim terminalu, uruchom symulator stacji (upewnij się, że backend działa):
    ```bash
    python station_simulator.py
    ```
8.  Przejdź do `http://localhost:3000` i zaloguj się.

## Funkcjonalności

*   **Autentykacja:** Logowanie użytkownika.
*   **Monitorowanie:** Wyświetlanie statusu stacji (dostępna, zajęta, ładuje).
*   **Zdalne sterowanie:** Możliwość ręcznego rozpoczęcia i zatrzymania sesji ładowania.
*   **Historia sesji:** Wyświetlanie listy zakończonych sesji.
*   **Symulacja:** Realistyczna symulacja działania stacji EV.