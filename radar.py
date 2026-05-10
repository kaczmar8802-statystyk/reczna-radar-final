import streamlit as st
import http.client
import json
import pandas as pd
from datetime import datetime, timezone
import io

# --- KONFIGURACJA ---
# TUTAJ WKLEJ SWÓJ KLUCZ (Z PANELU API-SPORTS)
API_KEY = "059a79179d695df1668bd254f6421762"
HOST = "v3.handball.api-sports.io"

st.set_page_config(page_title="GIGA RADAR RĘCZNA", layout="wide")

def api_call(endpoint):
    # Czyścimy dane z ewentualnych spacji
    k = API_KEY.strip()
    h = "v3.handball.api-sports.io"
    try:
        conn = http.client.HTTPSConnection(h, timeout=25)
        headers = {
            'x-rapidapi-key': k,
            'x-rapidapi-host': h
        }
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        return data
    except Exception as e:
        # Wyświetla błąd tylko w bocznym pasku, żeby nie psuć tabeli
        st.sidebar.error(f"Błąd sieci: {e}")
        return {"response": []}

def check_match_alert(date_str):
    if not date_str: return "---", ""
    try:
        match_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        diff = match_dt - now
        display_date = match_dt.strftime("%d.%m %H:%M")
        alert = "⏳" if 0 < diff.total_seconds() < 172800 else ""
        if diff.total_seconds() <= 0: alert = "⚽"
        return display_date, alert
    except: return "---", ""

st.title("🤾‍♂️ GIGA RADAR RĘCZNA (P/NP)")
st.write("Skanuje serie Parzyste/Nieparzyste ze wszystkich meczów (Liga + Puchary + Play-offy).")

# --- BAZA LIG ---
BAZA_LIG = {
    "NIEMCY": {"🇩🇪 Bundesliga 1": 78, "🇩🇪 Bundesliga 2": 79},
    "HISZPANIA": {"🇪🇸 Liga ASOBAL (1.L)": 117, "🇪🇸 Div. de Plata (2.L)": 118},
    "POLSKA": {"🇵🇱 Superliga (1.L)": 106, "🇵🇱 I Liga (2.L)": 107},
    "FRANCJA": {"🇫🇷 Starligue (1.L)": 61, "🇫🇷 Proligue (2.L)": 62},
    "DANIA": {"🇩🇰 Håndboldligaen (1.L)": 90, "🇩🇰 1. Division (2.L)": 91}
}

wybrane_ligi = []
cols = st.columns(len(BAZA_LIG))
for i, (kraj, ligi) in enumerate(BAZA_LIG.items()):
    with cols[i]:
        st.write(f"**{kraj}**")
        sel = st.multiselect(f"Ligi:", list(ligi.keys()), key=f"s_{kraj}")
        wybrane_ligi.extend(sel)

if st.button("🚀 URUCHOM GLOBALNY SKAN"):
    if not wybrane_ligi:
        st.warning("Wybierz ligi do skanowania!")
    else:
        results = []
        pb = st.progress(0)
        MAPA_ID = {k: v for d in BAZA_LIG.values() for k, v in d.items()}
        
        for idx, liga_nazwa in enumerate(wybrane_ligi):
            l_id = MAPA_ID[liga_nazwa]
            
            # Pobieramy Team ID dla sezonu 2024 lub 2025
            t_data = api_call(f"/teams?league={l_id}&season=2024")
            if not t_data.get('response'):
                t_data = api_call(f"/teams?league={l_id}&season=2025")
            
            teams = t_data.get('response', [])
            for t_entry in teams:
                tid, tname = t_entry['id'], t_entry['name']
                
                # Skanujemy ostatnie 15 meczów drużyny (WSZYSTKIE ROZGRYWKI)
                hist = api_call(f"/games?team={tid}&last=15")
                games = hist.get('response', [])
                
                sums = []
                for g in games:
                    if g['status']['short'] in ['FT', 'AET', 'PEN']:
                        try:
                            # Sumowanie goli w piłce ręcznej
                            sums.append(g['scores']['home'] + g['scores']['away'])
                        except: continue
                
                if len(sums) < 2: continue

                # Liczenie serii od najnowszego meczu
                snp = next((i for i, s in enumerate(sums) if s % 2 == 0), len(sums))
                sp = next((i for i, s in enumerate(sums) if s % 2 != 0), len(sums))
                
                typ = ""
                if snp >= 2: typ = "NIEPARZYSTE"
                elif sp >= 2: typ = "PARZYSTE"

                if typ:
                    # Sprawdzanie następnego meczu
                    n_match = api_call(f"/games?team={tid}&next=1")
                    m_date, m_alert = "---", "❄️"
                    if n_match.get('response'):
                        res = n_match['response'] if isinstance(n_match['response'], list) else n_match['response']
                        m_date, m_alert = check_match_alert(res['date'])
                        m_date = f"{m_date} ({res['league']['name']})"
                    
                    results.append({
                        "Drużyna": tname,
                        "Liga Baza": liga_nazwa,
                        "P": str(snp) if snp > 0 else "",
                        "NP": str(sp) if sp > 0 else "",
                        "Graj na": typ,
                        "Kiedy": m_date,
                        "Status": m_alert,
                        "Siła": max(snp, sp)
                    })
            
            pb.progress((idx + 1) / len(wybrane_ligi))
        
        if results:
            df = pd.DataFrame(results).sort_values("Siła", ascending=False)
            st.dataframe(df.drop(columns=["Siła"]), use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.drop(columns=["Siła"]).to_excel(writer, index=False)
            st.download_button("📥 POBIERZ RAPORT EXCEL", output.getvalue(), "reczna_global.xlsx")
        else:
            st.info("Brak aktywnych serii (min. 2).")
