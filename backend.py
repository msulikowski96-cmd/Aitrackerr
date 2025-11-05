# backend.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
import json
import asyncio
import logging

# --- KONFIGURACJA ---
SECRET_KEY = "your-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# --- BAZA DANYCH ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./ev_stations.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- HASHER HASŁ ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- MODELE PYDANTIC (do walidacji danych wejściowych) ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str = None

class UserCreate(BaseModel):
    username: str
    password: str

class StartChargingRequest(BaseModel):
    station_id: str
    car_id: str

class StopChargingRequest(BaseModel):
    station_id: str

# --- MODELE BAZY DANYCH ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)

class ChargingSession(Base):
    __tablename__ = "charging_sessions"
    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String, index=True)
    car_id = Column(String, index=True)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)
    kwh_delivered = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True) # Czy trwa sesja

Base.metadata.create_all(bind=engine)

# --- FUNKCJE POMOCNICZE ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def authenticate_user(db: Session, username: str, password: str):
    user = get_user(db, username)
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nieprawidłowy token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nieprawidłowy token")
    user = get_user(db, username=username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Użytkownik nie istnieje")
    return user

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- MANAGER STACJI (Udoskonalony) ---
class StationManager:
    def __init__(self):
        self.stations = {}
        self.connections = {}
        self.active_sessions = {} # station_id -> session_id

    def register_station(self, station_id: str, ws_connection):
        self.stations[station_id] = {"status": "available", "car_id": None, "current_kwh": 0.0, "is_charging": False}
        self.connections[station_id] = ws_connection
        logging.info(f"Stacja {station_id} zarejestrowana.")

    def update_station_status(self, station_id: str, data: dict):
        if station_id in self.stations:
            # Zaktualizuj dane tylko jeśli sesja nadal aktywna
            if self.stations[station_id]["is_charging"]:
                self.stations[station_id].update(data)
                logging.info(f"Status stacji {station_id} zaktualizowany: {data}")
            else:
                logging.warning(f"Otrzymano dane z nieaktywnej stacji {station_id}")

    def get_station_status(self, station_id: str):
        return self.stations.get(station_id, {})

    def get_all_stations_status(self):
        return self.stations

    def start_charging_session(self, station_id: str, car_id: str, db: Session):
        if station_id in self.stations and self.stations[station_id]["status"] == "available":
            # Zapisz sesję do bazy
            db_session = ChargingSession(station_id=station_id, car_id=car_id, is_active=True)
            db.add(db_session)
            db.commit()
            db.refresh(db_session)

            # Zaktualizuj stan stacji
            self.stations[station_id].update({
                "status": "occupied",
                "car_id": car_id,
                "is_charging": True
            })
            self.active_sessions[station_id] = db_session.id
            logging.info(f"Rozpoczęto ładowanie dla stacji {station_id}, auto {car_id}, sesja {db_session.id}")
            return True
        return False

    def stop_charging_session(self, station_id: str, db: Session):
        if station_id in self.active_sessions:
            session_id = self.active_sessions[station_id]
            db_session = db.query(ChargingSession).filter(ChargingSession.id == session_id, ChargingSession.is_active == True).first()
            if db_session:
                db_session.end_time = datetime.utcnow()
                db_session.is_active = False
                db_session.kwh_delivered = self.stations[station_id].get("current_kwh", 0.0)
                db.commit()

                # Zaktualizuj stan stacji
                self.stations[station_id].update({
                    "status": "available",
                    "car_id": None,
                    "current_kwh": 0.0,
                    "is_charging": False
                })
                del self.active_sessions[station_id]
                logging.info(f"Zakończono sesję {session_id} dla stacji {station_id}")
                return True
        return False

station_manager = StationManager()

# --- APLIKACJA FASTAPI ---
app = FastAPI(title="System Zarządzania Stacjami EV", description="Prototyp systemu do monitorowania i zarządzania stacjami EV.", version="1.0.0")

# --- MIDDLEWARE ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Uwaga: Zmień na konkretne adresy frontendu w produkcji
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ENDPOINTY API ---
@app.on_event("startup")
def startup_event():
    db = next(get_db())
    admin_user = get_user(db, "admin")
    if not admin_user:
        hashed_password = get_password_hash("admin123") # Zmień hasło!
        admin = User(username="admin", hashed_password=hashed_password)
        db.add(admin)
        db.commit()
        logging.info("Utworzono domyślnego użytkownika 'admin' z hasłem 'admin123'")
    db.close()

@app.post("/token", response_model=Token)
def login(user_credentials: UserCreate, db: Session = Depends(get_db)):
    user = authenticate_user(db, user_credentials.username, user_credentials.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nieprawidłowe dane logowania")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/stations")
def get_stations(current_user: User = Depends(get_current_user)):
    return station_manager.get_all_stations_status()

@app.get("/sessions")
def get_sessions(skip: int = 0, limit: int = 100, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.query(ChargingSession).offset(skip).limit(limit).all()
    return sessions

@app.post("/stations/{station_id}/start_charging")
def start_charging(request: StartChargingRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    success = station_manager.start_charging_session(request.station_id, request.car_id, db)
    if success:
        return {"message": f"Rozpoczęto ładowanie na stacji {request.station_id} dla auta {request.car_id}"}
    else:
        raise HTTPException(status_code=400, detail="Nie można rozpocząć ładowania")

@app.post("/stations/{station_id}/stop_charging")
def stop_charging(request: StopChargingRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    success = station_manager.stop_charging_session(request.station_id, db)
    if success:
        return {"message": f"Zatrzymano ładowanie na stacji {request.station_id}"}
    else:
        raise HTTPException(status_code=400, detail="Nie można zatrzymać ładowania")

# --- WEBSOCKET DLA STACJI ---
@app.websocket("/ws/station/{station_id}")
async def websocket_endpoint(websocket: WebSocket, station_id: str):
    await websocket.accept()
    station_manager.register_station(station_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                logging.error(f"Nieprawidłowy JSON od stacji {station_id}: {data}")
                continue

            # Przetwarzanie wiadomości od stacji
            if message.get("type") == "status_update":
                station_manager.update_station_status(station_id, {
                    "status": message.get("status", "unknown"),
                    "car_id": message.get("car_id"),
                    "current_kwh": message.get("current_kwh", 0.0)
                })
            elif message.get("type") == "charge_complete":
                # Zakończenie sesji inicjowane przez stację
                success = station_manager.stop_charging_session(station_id, next(get_db()))
                if success:
                    logging.info(f"Stacja {station_id} zgłosiła zakończenie sesji.")
                else:
                    logging.warning(f"Stacja {station_id} zgłosiła zakończenie, ale nie znaleziono aktywnej sesji.")

    except WebSocketDisconnect:
        logging.info(f"Stacja {station_id} rozłączona.")
        if station_id in station_manager.stations:
            del station_manager.stations[station_id]
        if station_id in station_manager.connections:
            del station_manager.connections[station_id]

if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="127.0.0.1", port=8000)