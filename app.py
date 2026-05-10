import streamlit as st
import http.client
import json
import pandas as pd
from datetime import datetime, timezone
import io

# --- KONFIGURACJA API ---
API_KEY = "059a79179d695df1668bd254f6421762" 
HOST = "v3.handball.api-sports.io"

st.set_page_config(page_title="RADAR RĘCZNA", layout="wide")

BAZA_LIG = {
    "NIEMCY": {"🇩🇪 Bundesliga 1": 78, "🇩🇪 Bundesliga 2": 79},
    "HISZPANIA": {"🇪🇸 Liga ASOBAL (1.L)": 117, "🇪🇸 Division de Plata (2.L)": 118},
    "POLSKA": {"🇵🇱 Superliga (1.L)": 106, "🇵🇱 I Liga (2.L)": 107},
    "FRANCJA": {"🇫🇷 Starligue (1.L)": 61, "🇫🇷 Proligue (2.L)": 62},
    "DANIA": {"🇩🇰 Håndboldligaen (1.L)": 90, "🇩🇰 1. Division (2.L)": 91}
}

def api_call(endpoint):
    try:
        conn = http.client.HTTPSConnection(HOST)
        headers = {'x-rapidapi-key': API_KEY.strip(), 'x-rapidapi-host': HOST}
        conn.request("GET", endpoint, headers=headers)
        return json.loads(conn.getresponse().read().decode("utf-8"))
    except: return {"response": []}

st.title("🤾‍♂️ GIGA RADAR RĘCZNA (P/NP)")

wybrane_ligi = []
cols = st.columns(len(BAZA_LIG))
for i, (kraj, ligi) in enumerate(BAZA_LIG.items()):
    with cols[i]:
        st.write(f"**{kraj}**")
        sel = st.multiselect("Ligi:", list(ligi.keys()), key=f"s_{kraj}")
        wybrane_ligi.extend(sel)

if st.button("🚀 URUCHOM SKAN"):
    if not wybrane_ligi: st.warning("Wybierz ligi!")
    else:
        results = []
        pb = st.progress(0)
        MAPA_ID = {k: v for d in BAZA_LIG.values() for k, v in d.items()}
        for idx, liga_nazwa in enumerate(wybrane_ligi):
            l_id = MAPA_ID[liga_nazwa]
            t_data = api_call(f"/teams?league={l_id}&season=2024")
            if not t_data.get('response'): t_data = api_call(f"/teams?league={l_id}&season=2025")
            for t_entry in t_data.get('response', []):
                tid, tname = t_entry['id'], t_entry['name']
                hist = api_call(f"/games?team={tid}&last=15")
                games = hist.get('response', [])
                sums = [g['scores']['home'] + g['scores']['away'] for g in games if g['status']['short'] in ['FT', 'AET', 'PEN']]
                if not sums: continue
                snp = next((i for i, s in enumerate(sums) if s % 2 == 0), len(sums))
                sp = next((i for i, s in enumerate(sums) if s % 2 != 0), len(sums))
                typ = "NIEPARZYSTE" if snp >= 2 else "PARZYSTE" if sp >= 2 else ""
                if typ:
                    results.append({"Drużyna": tname, "Liga": liga_nazwa, "P": snp, "NP": sp, "Graj na": typ, "Siła": max(snp, sp)})
            pb.progress((idx + 1) / len(wybrane_ligi))
        if results:
            df = pd.DataFrame(results).sort_values("Siła", ascending=False)
            st.dataframe(df.drop(columns=["Siła"]), use_container_width=True)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
                df.to_excel(wr, index=False)
            st.download_button("📥 POBIERZ EXCEL", buf.getvalue(), "reczna_radar.xlsx")
