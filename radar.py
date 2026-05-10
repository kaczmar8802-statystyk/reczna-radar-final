import streamlit as st
import http.client
import json
import pandas as pd
from datetime import datetime
import io

# --- KONFIGURACJA ---
API_KEY = "059a79179d695df1668bd254f6421762" # Wklej tu swój klucz!
HOST = "v3.handball.api-sports.io"

st.set_page_config(page_title="RADAR REZNA", layout="wide")

def api_call(endpoint):
    try:
        conn = http.client.HTTPSConnection(HOST, timeout=20)
        headers = {'x-rapidapi-key': API_KEY.strip(), 'x-rapidapi-host': HOST}
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        return json.loads(res.read().decode("utf-8"))
    except Exception as e:
        st.sidebar.error(f"Błąd sieci: {e}")
        return {"response": []}

st.title("🤾‍♂️ GIGA RADAR RĘCZNA")

BAZA_LIG = {
    "NIEMCY": {"D1": 78, "D2": 79},
    "HISZPANIA": {"ASOBAL": 117, "PLATA": 118},
    "POLSKA": {"SUPERLIGA": 106, "1.LIGA": 107},
    "FRANCJA": {"STARLIGUE": 61, "PROLIGUE": 62},
    "DANIA": {"LIGA": 90, "DIV1": 91}
}

wybrane = []
cols = st.columns(len(BAZA_LIG))
for i, (kraj, ligi) in enumerate(BAZA_LIG.items()):
    with cols[i]:
        st.write(f"**{kraj}**")
        s = st.multiselect("Ligi:", list(ligi.keys()), key=kraj)
        for n in s: wybrane.append((n, ligi[n]))

if st.button("🚀 URUCHOM SKAN"):
    if not wybrane: st.warning("Wybierz ligi!")
    else:
        results = []
        pb = st.progress(0)
        for idx, (l_nazwa, l_id) in enumerate(wybrane):
            # Pobierz drużyny
            t_data = api_call(f"/teams?league={l_id}&season=2024")
            if not t_data.get('response'): t_data = api_call(f"/teams?league={l_id}&season=2025")
            
            teams = t_data.get('response', [])
            for t in teams:
                tid, tname = t['id'], t['name']
                # Pobierz mecze
                h_data = api_call(f"/games?team={tid}&last=15")
                games = h_data.get('response', [])
                sums = [g['scores']['home'] + g['scores']['away'] for g in games if g['status']['short'] in ['FT', 'AET', 'PEN']]
                
                if len(sums) < 2: continue
                snp = next((i for i, s in enumerate(sums) if s % 2 == 0), len(sums))
                sp = next((i for i, s in enumerate(sums) if s % 2 != 0), len(sums))
                
                if snp >= 2 or sp >= 2:
                    typ = "NIEPARZYSTE" if snp >= 2 else "PARZYSTE"
                    results.append({"Drużyna": tname, "Liga": l_nazwa, "P": snp, "NP": sp, "Graj": typ, "Siła": max(snp, sp)})
            pb.progress((idx + 1) / len(wybrane))

        if results:
            df = pd.DataFrame(results).sort_values("Siła", ascending=False)
            st.dataframe(df.drop(columns=["Siła"]), use_container_width=True)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
                df.to_excel(wr, index=False)
            st.download_button("📥 POBIERZ EXCEL", buf.getvalue(), "handball.xlsx")
        else: st.info("Brak aktywnych serii.")
