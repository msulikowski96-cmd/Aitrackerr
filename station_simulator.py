# station_simulator.py

import asyncio
import websockets
import json
import time
import random
import threading

# Dane stacji - można łatwo dodać więcej
STATIONS = {
    "STATION_1": {"uri": "ws://localhost:8000/ws/station/STATION_1", "is_charging": False, "current_kwh": 0.0, "car_id": None},
    "STATION_2": {"uri": "ws://localhost:8000/ws/station/STATION_2", "is_charging": False, "current_kwh": 0.0, "car_id": None},
    "STATION_3": {"uri": "ws://localhost:8000/ws/station/STATION_3", "is_charging": False, "current_kwh": 0.0, "car_id": None},
}

async def simulate_station(station_id, uri):
    try:
        async with websockets.connect(uri) as websocket:
            print(f"[{station_id}] Połączono z backendem.")
            # Zainicjuj status jako dostępny
            init_msg = {
                "type": "status_update",
                "status": "available",
                "car_id": None,
                "current_kwh": 0.0
            }
            await websocket.send(json.dumps(init_msg))

            while True:
                # Odbieraj polecenia z backendu
                try:
                    command_data = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    command = json.loads(command_data)
                    if command.get("action") == "start_charging":
                        if not STATIONS[station_id]["is_charging"]:
                            STATIONS[station_id]["is_charging"] = True
                            STATIONS[station_id]["car_id"] = command["car_id"]
                            STATIONS[station_id]["current_kwh"] = 0.0
                            print(f"[{station_id}] Rozpoczęto ładowanie dla auta {command['car_id']}")
                    elif command.get("action") == "stop_charging":
                        if STATIONS[station_id]["is_charging"]:
                            STATIONS[station_id]["is_charging"] = False
                            kwh_delivered = STATIONS[station_id]["current_kwh"]
                            car_id = STATIONS[station_id]["car_id"]
                            STATIONS[station_id]["car_id"] = None
                            STATIONS[station_id]["current_kwh"] = 0.0
                            print(f"[{station_id}] Zakończono ładowanie dla auta {car_id}, doładowano {kwh_delivered:.2f} kWh")
                            # Wyślij zakończenie sesji
                            complete_msg = {
                                "type": "charge_complete",
                                "station_id": station_id,
                                "car_id": car_id,
                                "kwh_delivered": kwh_delivered
                            }
                            await websocket.send(json.dumps(complete_msg))
                            # Wyślij status dostępności
                            available_msg = {
                                "type": "status_update",
                                "status": "available",
                                "car_id": None,
                                "current_kwh": 0.0
                            }
                            await websocket.send(json.dumps(available_msg))
                except asyncio.TimeoutError:
                    # Brak komendy, kontynuuj symulację
                    pass

                # Symulacja postępu ładowania
                if STATIONS[station_id]["is_charging"]:
                    STATIONS[station_id]["current_kwh"] += random.uniform(0.1, 0.5)
                    # Wyślij aktualizację statusu
                    status_msg = {
                        "type": "status_update",
                        "status": "charging",
                        "car_id": STATIONS[station_id]["car_id"],
                        "current_kwh": round(STATIONS[station_id]["current_kwh"], 2)
                    }
                    await websocket.send(json.dumps(status_msg))
                    # Sprawdź, czy sesja się zakończyła
                    if STATIONS[station_id]["current_kwh"] >= random.uniform(10, 50):
                        # Zakończ sesję po osiągnięciu losowego progu
                        STATIONS[station_id]["is_charging"] = False
                        kwh_delivered = STATIONS[station_id]["current_kwh"]
                        car_id = STATIONS[station_id]["car_id"]
                        STATIONS[station_id]["car_id"] = None
                        STATIONS[station_id]["current_kwh"] = 0.0
                        print(f"[{station_id}] Symulacja: Zakończono sesję dla auta {car_id}, doładowano {kwh_delivered:.2f} kWh")
                        complete_msg = {
                            "type": "charge_complete",
                            "station_id": station_id,
                            "car_id": car_id,
                            "kwh_delivered": kwh_delivered
                        }
                        await websocket.send(json.dumps(complete_msg))
                        available_msg = {
                            "type": "status_update",
                            "status": "available",
                            "car_id": None,
                            "current_kwh": 0.0
                        }
                        await websocket.send(json.dumps(available_msg))

                await asyncio.sleep(2)

    except websockets.exceptions.ConnectionClosedOK:
        print(f"[{station_id}] Połączenie zamknięte.")
    except Exception as e:
        print(f"[{station_id}] Błąd symulacji: {e}")

async def main():
    tasks = []
    for station_id, config in STATIONS.items():
        task = asyncio.create_task(simulate_station(station_id, config["uri"]))
        tasks.append(task)

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())