// frontend/src/App.js

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

// Uproszczony komponent logowania
function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.post('http://localhost:8000/token', {
        username,
        password,
      }, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      });
      localStorage.setItem('access_token', response.data.access_token);
      onLogin(response.data.access_token);
    } catch (err) {
      setError('Nieprawidłowe dane logowania');
    }
  };

  return (
    <div style={{ padding: '20px', maxWidth: '400px', margin: 'auto' }}>
      <h2>Logowanie</h2>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <form onSubmit={handleSubmit}>
        <div>
          <label>Użytkownik: </label>
          <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} required />
        </div>
        <div>
          <label>Hasło: </label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <button type="submit">Zaloguj</button>
      </form>
    </div>
  );
}

function App() {
  const [token, setToken] = useState(localStorage.getItem('access_token'));
  const [stations, setStations] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [newCarId, setNewCarId] = useState('');
  const [selectedStation, setSelectedStation] = useState('');
  const [loading, setLoading] = useState(false);

  const api = axios.create({
    baseURL: 'http://localhost:8000',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  const fetchStations = async () => {
    try {
      const res = await api.get('/stations');
      setStations(res.data);
    } catch (error) {
      console.error("Błąd pobierania stacji:", error);
      if (error.response?.status === 401) {
        handleLogout();
      }
    }
  };

  const fetchSessions = async () => {
    try {
      const res = await api.get('/sessions');
      setSessions(res.data);
    } catch (error) {
      console.error("Błąd pobierania sesji:", error);
      if (error.response?.status === 401) {
        handleLogout();
      }
    }
  };

  useEffect(() => {
    if (token) {
      const fetchInitialData = async () => {
        await fetchStations();
        await fetchSessions();
      };
      fetchInitialData();

      const interval = setInterval(() => {
        fetchStations();
        fetchSessions();
      }, 5000);

      return () => clearInterval(interval);
    }
  }, [token]);

  const handleLogin = (token) => {
    setToken(token);
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    setToken(null);
  };

  const handleStartCharging = async () => {
    if (!selectedStation || !newCarId) return;
    setLoading(true);
    try {
      await api.post(`/stations/${selectedStation}/start_charging`, { station_id: selectedStation, car_id: newCarId });
      setNewCarId('');
      fetchStations(); // Odśwież stan
    } catch (error) {
      console.error("Błąd uruchamiania ładowania:", error);
    }
    setLoading(false);
  };

  const handleStopCharging = async (stationId) => {
    setLoading(true);
    try {
      await api.post(`/stations/${stationId}/stop_charging`, { station_id: stationId });
      fetchStations(); // Odśwież stan
    } catch (error) {
      console.error("Błąd zatrzymywania ładowania:", error);
    }
    setLoading(false);
  };

  if (!token) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="App">
      <header className="App-header">
        <h1>System Zarządzania Stacjami EV</h1>
        <button onClick={handleLogout} style={{ marginLeft: 'auto' }}>Wyloguj</button>
      </header>
      <main style={{ padding: '20px' }}>
        {/* Formularz do uruchamiania ładowania */}
        <section style={{ marginBottom: '20px', padding: '10px', background: 'rgba(255,255,255,0.05)' }}>
          <h2>Uruchom Ładowanie</h2>
          <div style={{ display: 'flex', gap: '10px' }}>
            <select value={selectedStation} onChange={(e) => setSelectedStation(e.target.value)}>
              <option value="">Wybierz stację</option>
              {Object.keys(stations).map(id => (
                <option key={id} value={id}>{id}</option>
              ))}
            </select>
            <input
              type="text"
              placeholder="ID auta"
              value={newCarId}
              onChange={(e) => setNewCarId(e.target.value)}
            />
            <button onClick={handleStartCharging} disabled={loading}>Rozpocznij</button>
          </div>
        </section>

        <section>
          <h2>Stanowiska</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '10px' }}>
            {Object.entries(stations).map(([id, status]) => (
              <div key={id} style={{ padding: '10px', border: '1px solid #ccc', borderRadius: '4px' }}>
                <h3>Stanowisko {id}</h3>
                <p>Status: <span style={{ color: status.status === 'available' ? 'green' : 'red' }}>{status.status}</span></p>
                <p>Auto: {status.car_id || 'Brak'}</p>
                <p>Doładowano: {status.current_kwh?.toFixed(2) || 0} kWh</p>
                {status.status !== 'available' && (
                  <button onClick={() => handleStopCharging(id)} disabled={loading}>Zatrzymaj</button>
                )}
              </div>
            ))}
          </div>
        </section>

        <section style={{ marginTop: '20px' }}>
          <h2>Ostatnie Sesje</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th>ID Stacji</th>
                <th>ID Samochodu</th>
                <th>Rozpoczęto</th>
                <th>Zakończono</th>
                <th>Doładowano (kWh)</th>
                <th>Aktywna?</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => (
                <tr key={session.id}>
                  <td>{session.station_id}</td>
                  <td>{session.car_id}</td>
                  <td>{session.start_time ? new Date(session.start_time).toLocaleString() : 'N/A'}</td>
                  <td>{session.end_time ? new Date(session.end_time).toLocaleString() : 'Trwa...'}</td>
                  <td>{session.kwh_delivered?.toFixed(2)}</td>
                  <td>{session.is_active ? 'Tak' : 'Nie'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  );
}

export default App;