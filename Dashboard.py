import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
import pytz
import warnings
warnings.filterwarnings('ignore')

# Configuration de la page
st.set_page_config(
    page_title="Tracker Bourse France - Euronext Paris",
    page_icon="🇫🇷",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration des fuseaux horaires
PARIS_TZ = pytz.timezone('Europe/Paris')
NY_TZ = pytz.timezone('America/New_York')

# Style CSS personnalisé
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #0055A4;
        text-align: center;
        margin-bottom: 2rem;
        font-family: 'Montserrat', sans-serif;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .stock-price {
        font-size: 2.5rem;
        font-weight: bold;
        color: #0055A4;
        text-align: center;
    }
    .stock-change-positive {
        color: #00cc96;
        font-size: 1.2rem;
        font-weight: bold;
    }
    .stock-change-negative {
        color: #ef553b;
        font-size: 1.2rem;
        font-weight: bold;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .alert-box {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .alert-success {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .alert-warning {
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        color: #856404;
    }
    .portfolio-table {
        font-size: 0.9rem;
    }
    .stButton>button {
        width: 100%;
    }
    .timezone-badge {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
        padding: 0.5rem 1rem;
        margin: 1rem 0;
        font-size: 0.9rem;
    }
    .france-market-note {
        background: linear-gradient(135deg, #0055A4 0%, #FFFFFF 50%, #EF4135 100%);
        color: white;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
    }
    .cac40-badge {
        background-color: #ED2939;
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 1rem;
        font-weight: bold;
        display: inline-block;
    }
    .symbol-update {
        background-color: #e7f3ff;
        border-left: 4px solid #2196F3;
        padding: 0.5rem 1rem;
        margin: 0.5rem 0;
        font-size: 0.9rem;
        border-radius: 0.25rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialisation des variables de session
if 'price_alerts' not in st.session_state:
    st.session_state.price_alerts = []

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}

# Dictionnaire de correspondance des anciens symboles vers les nouveaux
SYMBOL_MAPPING = {
    'ACA.PA': 'AC.PA',      # Crédit Agricole
    'TOTF.PA': 'TTE.PA',     # TotalEnergies
    'FTE.PA': 'ORAN.PA',     # Orange
    'EDF.PA': None,          # Nationalisé - plus disponible
    'GLE.PA': 'GLE.PA',      # Société Générale (inchangé)
    'BNP.PA': 'BNP.PA',      # BNP Paribas (inchangé)
}

# WATCHLIST CORRIGÉE AVEC LES BONS SYMBOLES
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = [
        # CAC 40 - Symboles corrects
        'MC.PA',        # LVMH
        'OR.PA',        # L'Oréal
        'AC.PA',        # Crédit Agricole (CORRIGÉ - était ACA.PA)
        'BNP.PA',       # BNP Paribas
        'GLE.PA',       # Société Générale
        'AIR.PA',       # Airbus
        'SAF.PA',       # Safran
        'RMS.PA',       # Hermès
        'SAN.PA',       # Sanofi
        'TTE.PA',       # TotalEnergies (CORRIGÉ - était TOTF.PA)
        'SU.PA',        # Schneider Electric
        'CAP.PA',       # Capgemini
        'DSY.PA',       # Dassault Systèmes
        'ENGI.PA',      # Engie
        'ORAN.PA',      # Orange (CORRIGÉ - était FTE.PA)
        'VIV.PA',       # Vivendi
        'VIE.PA',       # Veolia
        'RNO.PA',       # Renault
        'STLAP.PA',     # Stellantis
        'AI.PA',        # Air Liquide
        'KER.PA',       # Kering
        'CDI.PA',       # Christian Dior
        'DG.PA',        # Vinci
        'LR.PA',        # Legrand
        'EL.PA',        # EssilorLuxottica
        'BN.PA',        # Danone
        'PUB.PA',       # Publicis
        'SGO.PA',       # Saint-Gobain
        'ML.PA',        # Michelin
        'ATO.PA',       # Atos
        'HO.PA',        # Thales
        'SW.PA',        # Sodexo
        'ERF.PA',       # Eramet
        'DEC.PA',       # JCDecaux
        'NOKIA.PA',     # Nokia (Paris)
    ]

if 'notifications' not in st.session_state:
    st.session_state.notifications = []

if 'email_config' not in st.session_state:
    st.session_state.email_config = {
        'enabled': False,
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'email': '',
        'password': ''
    }

# Mapping des suffixes Euronext
FRENCH_EXCHANGES = {
    '.PA': 'Euronext Paris',
    '.AS': 'Euronext Amsterdam',
    '.BR': 'Euronext Brussels',
    '.L': 'London Stock Exchange',
    '.MI': 'Borsa Italiana',
    '.DE': 'Deutsche Börse',
    '': 'US Listed'
}

# Jours fériés français
FRENCH_HOLIDAYS_2024 = [
    '2024-01-01',  # Jour de l'An
    '2024-04-01',  # Lundi de Pâques
    '2024-05-01',  # Fête du Travail
    '2024-05-08',  # Victoire 1945
    '2024-05-09',  # Ascension
    '2024-05-20',  # Pentecôte
    '2024-07-14',  # Fête Nationale
    '2024-08-15',  # Assomption
    '2024-11-01',  # Toussaint
    '2024-11-11',  # Armistice
    '2024-12-25',  # Noël
]

# Actions non cotées ou problématiques avec suggestions
DELISTED_STOCKS = {
    'EDF.PA': 'Nationalisé en 2023 - Plus disponible',
    'ACA.PA': 'Utilisez AC.PA (Crédit Agricole)',
    'TOTF.PA': 'Utilisez TTE.PA (TotalEnergies)',
    'FTE.PA': 'Utilisez ORAN.PA (Orange)',
}

def validate_and_fix_symbol(symbol):
    """Valide et corrige automatiquement les symboles obsolètes"""
    if symbol in SYMBOL_MAPPING:
        new_symbol = SYMBOL_MAPPING[symbol]
        if new_symbol is None:
            return None, f"❌ {symbol} n'est plus disponible"
        return new_symbol, f"🔄 {symbol} → {new_symbol}"
    return symbol, None

# Titre principal
st.markdown("<h1 class='main-header'>🇫🇷 Tracker Bourse France - Euronext Paris en Temps Réel</h1>", unsafe_allow_html=True)

# Bannière de mise à jour des symboles
st.markdown("""
<div class='symbol-update'>
    <b>🔄 Mise à jour des symboles :</b><br>
    - ACA.PA → AC.PA (Crédit Agricole)<br>
    - TOTF.PA → TTE.PA (TotalEnergies)<br>
    - FTE.PA → ORAN.PA (Orange)<br>
    - EDF.PA n'est plus coté (nationalisé en 2023)
</div>
""", unsafe_allow_html=True)

# Bannière de fuseau horaire
current_time_paris = datetime.now(PARIS_TZ)
current_time_ny = datetime.now(NY_TZ)

st.markdown(f"""
<div class='timezone-badge'>
    <b>🕐 Fuseaux horaires :</b><br>
    🇫🇷 Heure Paris : {current_time_paris.strftime('%H:%M:%S')} (UTC+2)<br>
    🇺🇸 Heure NY : {current_time_ny.strftime('%H:%M:%S')} (UTC-4/UTC-5)<br>
    📍 Tous les horaires affichés en heure de Paris (UTC+2)
</div>
""", unsafe_allow_html=True)

# Note sur les marchés français
st.markdown("""
<div class='france-market-note'>
    <b>🇫🇷 Euronext Paris :</b> 
    <span class='cac40-badge'>CAC 40</span><br>
    - Actions françaises: suffixe .PA (ex: MC.PA, OR.PA, AIR.PA)<br>
    - Horaires trading: Lundi-Vendredi 09:00 - 17:30 (heure Paris)<br>
    - Pré-ouverture: 07:15 - 09:00 | Après-clôture: 17:30 - 20:00
</div>
""", unsafe_allow_html=True)

# Sidebar pour la navigation
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/paris.png", width=80)
    st.title("Navigation")
    
    menu = st.radio(
        "Choisir une section",
        ["📈 Tableau de bord", 
         "💰 Portefeuille virtuel", 
         "🔔 Alertes de prix",
         "📧 Notifications email",
         "📤 Export des données",
         "🤖 Prédictions ML",
         "🇫🇷 Indices CAC 40"]
    )
    
    st.markdown("---")
    
    # Configuration commune
    st.subheader("⚙️ Configuration")
    st.caption(f"🕐 Fuseau : Heure de Paris (UTC+2)")
    
    # Créer une liste de symboles avec noms lisibles
    symbol_display = {
        'MC.PA': 'LVMH',
        'OR.PA': "L'Oréal",
        'AC.PA': 'Crédit Agricole',
        'BNP.PA': 'BNP Paribas',
        'GLE.PA': 'Société Générale',
        'AIR.PA': 'Airbus',
        'SAF.PA': 'Safran',
        'RMS.PA': 'Hermès',
        'SAN.PA': 'Sanofi',
        'TTE.PA': 'TotalEnergies',
        'SU.PA': 'Schneider Electric',
        'CAP.PA': 'Capgemini',
        'DSY.PA': 'Dassault Systèmes',
        'ENGI.PA': 'Engie',
        'ORAN.PA': 'Orange',
        'VIV.PA': 'Vivendi',
        'VIE.PA': 'Veolia',
        'RNO.PA': 'Renault',
        'STLAP.PA': 'Stellantis',
        'AI.PA': 'Air Liquide',
        'KER.PA': 'Kering',
        'CDI.PA': 'Christian Dior',
        'DG.PA': 'Vinci',
        'LR.PA': 'Legrand',
        'EL.PA': 'EssilorLuxottica',
        'BN.PA': 'Danone',
        'PUB.PA': 'Publicis',
        'SGO.PA': 'Saint-Gobain',
        'ML.PA': 'Michelin',
    }
    
    # Options pour le selectbox avec noms lisibles
    options_with_names = [f"{sym} - {symbol_display.get(sym, '')}" for sym in st.session_state.watchlist]
    options_with_names.append("Autre...")
    
    selected_option = st.selectbox(
        "Symbole principal",
        options=options_with_names,
        index=0
    )
    
    # Extraire le symbole de l'option sélectionnée
    if selected_option == "Autre...":
        symbol_input = st.text_input("Entrer un symbole", value="MC.PA").upper()
        
        # Vérifier et corriger automatiquement
        fixed_symbol, message = validate_and_fix_symbol(symbol_input)
        if message:
            if fixed_symbol is None:
                st.error(message)
                symbol = symbol_input
            else:
                st.info(message)
                symbol = fixed_symbol
        else:
            symbol = symbol_input
            
        # Ajouter à la watchlist si valide
        if symbol and symbol not in st.session_state.watchlist and symbol not in DELISTED_STOCKS:
            # Tester si le symbole est valide
            try:
                test_ticker = yf.Ticker(symbol)
                test_hist = test_ticker.history(period='1d')
                if not test_hist.empty:
                    st.session_state.watchlist.append(symbol)
                    st.success(f"✅ {symbol} ajouté à la watchlist")
                else:
                    st.error(f"❌ {symbol} n'est pas un symbole valide")
            except:
                st.error(f"❌ Erreur lors de la validation de {symbol}")
    else:
        # Extraire le symbole de l'option sélectionnée
        symbol = selected_option.split(" - ")[0]
    
    # Aide sur les symboles
    with st.expander("📌 Aide sur les symboles"):
        st.markdown("""
        **Symboles CAC 40 corrects:**
        - AC.PA (Crédit Agricole) - anciennement ACA.PA
        - TTE.PA (TotalEnergies) - anciennement TOTF.PA
        - ORAN.PA (Orange) - anciennement FTE.PA
        - AI.PA (Air Liquide)
        - MC.PA (LVMH)
        - OR.PA (L'Oréal)
        
        **Non disponibles:**
        - EDF.PA (nationalisé en 2023)
        """)
    
    # Note sur les suffixes
    st.caption("""
    📍 Suffixes Euronext:
    - .PA: Paris
    - .AS: Amsterdam
    - .BR: Bruxelles
    - .L: Londres
    """)
    
    # Période et intervalle
    col1, col2 = st.columns(2)
    with col1:
        period = st.selectbox(
            "Période",
            options=["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"],
            index=2
        )
    
    with col2:
        interval_map = {
            "1m": "1 minute", "5m": "5 minutes", "15m": "15 minutes",
            "30m": "30 minutes", "1h": "1 heure", "1d": "1 jour",
            "1wk": "1 semaine", "1mo": "1 mois"
        }
        interval = st.selectbox(
            "Intervalle",
            options=list(interval_map.keys()),
            format_func=lambda x: interval_map[x],
            index=4 if period == "1d" else 6
        )
    
    # Auto-refresh
    auto_refresh = st.checkbox("Actualisation automatique", value=False)
    if auto_refresh:
        refresh_rate = st.slider(
            "Fréquence (secondes)",
            min_value=5,
            max_value=60,
            value=30,
            step=5
        )

# Fonctions utilitaires
@st.cache_data(ttl=300)
def load_stock_data(symbol, period, interval):
    """Charge les données boursières avec correction automatique"""
    try:
        # Vérifier et corriger le symbole si nécessaire
        original_symbol = symbol
        fixed_symbol, message = validate_and_fix_symbol(symbol)
        
        if fixed_symbol is None:
            st.error(f"❌ {original_symbol} - {message}")
            return None, None
        elif fixed_symbol != original_symbol:
            st.info(f"🔄 Correction automatique: {original_symbol} → {fixed_symbol}")
            symbol = fixed_symbol
        
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)
        info = ticker.info
        
        # Convertir l'index en heure de Paris
        if not hist.empty:
            if hist.index.tz is None:
                hist.index = hist.index.tz_localize('UTC').tz_convert(PARIS_TZ)
            else:
                hist.index = hist.index.tz_convert(PARIS_TZ)
        
        return hist, info
    except Exception as e:
        st.error(f"Erreur: {e}")
        return None, None

def get_exchange(symbol):
    """Détermine l'échange pour un symbole"""
    if symbol.endswith('.PA'):
        return 'Euronext Paris'
    elif symbol.endswith('.AS'):
        return 'Euronext Amsterdam'
    elif symbol.endswith('.BR'):
        return 'Euronext Brussels'
    elif symbol.endswith('.L'):
        return 'London Stock Exchange'
    elif symbol.endswith('.MI'):
        return 'Borsa Italiana'
    elif symbol.endswith('.DE'):
        return 'Deutsche Börse'
    else:
        return 'US/Global'

def get_currency(symbol):
    """Détermine la devise pour un symbole"""
    if any(symbol.endswith(suffix) for suffix in ['.PA', '.AS', '.BR', '.MI', '.DE']):
        return 'EUR'
    elif symbol.endswith('.L'):
        return 'GBP'
    else:
        return 'USD'

def format_currency(value, symbol):
    """Formate la monnaie selon le symbole"""
    currency = get_currency(symbol)
    if currency == 'EUR':
        return f"€{value:,.2f}"
    elif currency == 'GBP':
        return f"£{value:,.2f}"
    else:
        return f"${value:,.2f}"

def send_email_alert(subject, body, to_email):
    """Envoie une notification par email"""
    if not st.session_state.email_config['enabled']:
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = st.session_state.email_config['email']
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(
            st.session_state.email_config['smtp_server'], 
            st.session_state.email_config['smtp_port']
        )
        server.starttls()
        server.login(
            st.session_state.email_config['email'],
            st.session_state.email_config['password']
        )
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Erreur d'envoi: {e}")
        return False

def check_price_alerts(current_price, symbol):
    """Vérifie les alertes de prix"""
    triggered = []
    for alert in st.session_state.price_alerts:
        if alert['symbol'] == symbol:
            if alert['condition'] == 'above' and current_price >= alert['price']:
                triggered.append(alert)
            elif alert['condition'] == 'below' and current_price <= alert['price']:
                triggered.append(alert)
    
    return triggered

def get_market_status():
    """Détermine le statut des marchés français"""
    paris_now = datetime.now(PARIS_TZ)
    paris_hour = paris_now.hour
    paris_minute = paris_now.minute
    paris_weekday = paris_now.weekday()
    paris_date = paris_now.strftime('%Y-%m-%d')
    
    # Weekend (samedi = 5, dimanche = 6)
    if paris_weekday >= 5:
        return "Fermé (weekend)", "🔴"
    
    # Jours fériés
    if paris_date in FRENCH_HOLIDAYS_2024:
        return "Fermé (jour férié)", "🔴"
    
    # Horaires Euronext: 09:00 - 17:30
    if 9 <= paris_hour < 17:
        return "Ouvert", "🟢"
    elif paris_hour == 17 and paris_minute <= 30:
        return "Ouvert", "🟢"
    elif 7 <= paris_hour < 9:
        return "Pré-ouverture", "🟡"
    elif 17 < paris_hour < 20:
        return "Après-clôture", "🟡"
    else:
        return "Fermé", "🔴"

def safe_get_metric(hist, metric, index=-1):
    """Récupère une métrique en toute sécurité"""
    try:
        if hist is not None and not hist.empty and len(hist) > abs(index):
            return hist[metric].iloc[index]
        return 0
    except:
        return 0

# Chargement des données avec correction automatique
hist, info = load_stock_data(symbol, period, interval)

# Vérification si les données sont disponibles
if hist is None or hist.empty:
    st.warning(f"⚠️ Impossible de charger les données pour {symbol}. Vérifiez que le symbole est correct.")
    
    # Suggestions spécifiques
    if symbol in DELISTED_STOCKS:
        st.error(f"❌ {DELISTED_STOCKS[symbol]}")
    elif symbol == 'ACA.PA':
        st.info("🔍 Le Crédit Agricole utilise maintenant le symbole **AC.PA**")
    elif symbol == 'TOTF.PA':
        st.info("🔍 TotalEnergies utilise maintenant le symbole **TTE.PA**")
    elif symbol == 'FTE.PA':
        st.info("🔍 Orange utilise maintenant le symbole **ORAN.PA**")
    
    current_price = 0
else:
    current_price = safe_get_metric(hist, 'Close')
    
    # Vérification des alertes
    triggered_alerts = check_price_alerts(current_price, symbol)
    for alert in triggered_alerts:
        st.balloons()
        st.success(f"🎯 Alerte déclenchée pour {symbol} à {format_currency(current_price, symbol)}")
        
        # Notification email
        if st.session_state.email_config['enabled']:
            subject = f"🚨 Alerte prix - {symbol}"
            body = f"""
            <h2>Alerte de prix déclenchée</h2>
            <p><b>Symbole:</b> {symbol}</p>
            <p><b>Prix actuel:</b> {format_currency(current_price, symbol)}</p>
            <p><b>Condition:</b> {alert['condition']} {format_currency(alert['price'], symbol)}</p>
            <p><b>Date:</b> {datetime.now(PARIS_TZ).strftime('%Y-%m-%d %H:%M:%S')} (heure Paris)</p>
            """
            send_email_alert(subject, body, st.session_state.email_config['email'])
        
        # Retirer l'alerte si elle est à usage unique
        if alert.get('one_time', False):
            st.session_state.price_alerts.remove(alert)

# ============================================================================
# SECTION 1: TABLEAU DE BORD
# ============================================================================
if menu == "📈 Tableau de bord":
    # Statut du marché
    market_status, market_icon = get_market_status()
    st.info(f"{market_icon} Marché Euronext Paris: {market_status}")
    
    if hist is not None and not hist.empty:
        # Métriques principales
        exchange = get_exchange(symbol)
        currency = get_currency(symbol)
        
        # Nom de l'entreprise si disponible
        company_name = info.get('longName', symbol) if info else symbol
        st.subheader(f"📊 {company_name} ({symbol}) - {exchange}")
        
        col1, col2, col3, col4 = st.columns(4)
        
        previous_close = safe_get_metric(hist, 'Close', -2) if len(hist) > 1 else current_price
        change = current_price - previous_close
        change_pct = (change / previous_close * 100) if previous_close != 0 else 0
        
        with col1:
            st.metric(
                label="Prix actuel",
                value=format_currency(current_price, symbol),
                delta=f"{change:.2f} ({change_pct:.2f}%)"
            )
        
        with col2:
            day_high = safe_get_metric(hist, 'High')
            st.metric("Plus haut", format_currency(day_high, symbol))
        
        with col3:
            day_low = safe_get_metric(hist, 'Low')
            st.metric("Plus bas", format_currency(day_low, symbol))
        
        with col4:
            volume = safe_get_metric(hist, 'Volume')
            if volume > 1e9:
                volume_formatted = f"{volume/1e9:.2f}B"
            elif volume > 1e6:
                volume_formatted = f"{volume/1e6:.2f}M"
            elif volume > 1e3:
                volume_formatted = f"{volume/1e3:.2f}K"
            else:
                volume_formatted = f"{volume:.0f}"
            st.metric("Volume", volume_formatted)
        
        # Dernière mise à jour
        st.caption(f"Dernière mise à jour: {hist.index[-1].strftime('%Y-%m-%d %H:%M:%S')} (heure Paris)")
        
        # Graphique principal
        st.subheader("📉 Évolution du prix")
        
        fig = go.Figure()
        
        # Chandeliers ou ligne selon l'intervalle
        if interval in ["1m", "5m", "15m", "30m", "1h"]:
            fig.add_trace(go.Candlestick(
                x=hist.index,
                open=hist['Open'],
                high=hist['High'],
                low=hist['Low'],
                close=hist['Close'],
                name='Prix',
                increasing_line_color='#00cc96',
                decreasing_line_color='#ef553b'
            ))
        else:
            fig.add_trace(go.Scatter(
                x=hist.index,
                y=hist['Close'],
                mode='lines',
                name='Prix',
                line=dict(color='#0055A4', width=2)
            ))
        
        # Ajouter les moyennes mobiles
        if len(hist) >= 20:
            ma_20 = hist['Close'].rolling(window=20).mean()
            fig.add_trace(go.Scatter(
                x=hist.index,
                y=ma_20,
                mode='lines',
                name='MA 20',
                line=dict(color='orange', width=1, dash='dash')
            ))
        
        if len(hist) >= 50:
            ma_50 = hist['Close'].rolling(window=50).mean()
            fig.add_trace(go.Scatter(
                x=hist.index,
                y=ma_50,
                mode='lines',
                name='MA 50',
                line=dict(color='purple', width=1, dash='dash')
            ))
        
        # Volume
        fig.add_trace(go.Bar(
            x=hist.index,
            y=hist['Volume'],
            name='Volume',
            yaxis='y2',
            marker=dict(color='lightgray', opacity=0.3)
        ))
        
        fig.update_layout(
            title=f"{symbol} - {period} (heure Paris)",
            yaxis_title=f"Prix ({'€' if currency=='EUR' else '£' if currency=='GBP' else '$'})",
            yaxis2=dict(
                title="Volume",
                overlaying='y',
                side='right',
                showgrid=False
            ),
            xaxis_title="Date (heure Paris)",
            height=600,
            hovermode='x unified',
            template='plotly_white'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Informations sur l'entreprise
        with st.expander("ℹ️ Informations sur l'entreprise"):
            if info:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Nom :** {info.get('longName', 'N/A')}")
                    st.write(f"**Secteur :** {info.get('sector', 'N/A')}")
                    st.write(f"**Industrie :** {info.get('industry', 'N/A')}")
                    st.write(f"**Site web :** {info.get('website', 'N/A')}")
                    st.write(f"**Bourse :** {exchange}")
                    st.write(f"**Devise :** {currency}")
                
                with col2:
                    market_cap = info.get('marketCap', 0)
                    if market_cap > 0:
                        if currency == 'EUR':
                            st.write(f"**Capitalisation :** €{market_cap:,.0f}")
                        elif currency == 'GBP':
                            st.write(f"**Capitalisation :** £{market_cap:,.0f}")
                        else:
                            st.write(f"**Capitalisation :** ${market_cap:,.0f}")
                    else:
                        st.write("**Capitalisation :** N/A")
                    
                    st.write(f"**P/E :** {info.get('trailingPE', 'N/A')}")
                    st.write(f"**Dividende :** {info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "**Dividende :** N/A")
                    st.write(f"**Beta :** {info.get('beta', 'N/A')}")
            else:
                st.write("Informations non disponibles")
    else:
        st.warning(f"Aucune donnée disponible pour {symbol}")

# ============================================================================
# SECTION 2: PORTEFEUILLE VIRTUEL
# ============================================================================
elif menu == "💰 Portefeuille virtuel":
    st.subheader("💰 Gestion de portefeuille virtuel - Actions Françaises")
    
    col1, col2 = st.columns([2, 1])
    
    with col2:
        st.markdown("### ➕ Ajouter une position")
        with st.form("add_position"):
            symbol_pf = st.text_input("Symbole", value="MC.PA").upper()
            
            # Vérifier et corriger automatiquement
            fixed_symbol, message = validate_and_fix_symbol(symbol_pf)
            if message and fixed_symbol:
                st.info(message)
                symbol_pf = fixed_symbol
            elif message and fixed_symbol is None:
                st.error(message)
            
            # Aide sur les suffixes
            st.caption("""
            Suffixes Euronext:
            - .PA: Paris
            - .AS: Amsterdam
            - .BR: Bruxelles
            """)
            
            shares = st.number_input("Nombre d'actions", min_value=0.01, step=0.01, value=1.0)
            buy_price = st.number_input("Prix d'achat (€)", min_value=0.01, step=0.01, value=100.0)
            
            if st.form_submit_button("Ajouter au portefeuille"):
                if symbol_pf and shares > 0 and symbol_pf not in DELISTED_STOCKS:
                    if symbol_pf not in st.session_state.portfolio:
                        st.session_state.portfolio[symbol_pf] = []
                    
                    st.session_state.portfolio[symbol_pf].append({
                        'shares': shares,
                        'buy_price': buy_price,
                        'date': datetime.now(PARIS_TZ).strftime('%Y-%m-%d %H:%M:%S')
                    })
                    st.success(f"✅ {shares} actions {symbol_pf} ajoutées")
    
    with col1:
        st.markdown("### 📊 Performance du portefeuille")
        
        if st.session_state.portfolio:
            portfolio_data = []
            total_value_eur = 0
            total_cost_eur = 0
            
            for symbol_pf, positions in st.session_state.portfolio.items():
                try:
                    # Vérifier si le symbole est toujours valide
                    if symbol_pf in DELISTED_STOCKS:
                        st.warning(f"⚠️ {symbol_pf} n'est plus coté")
                        continue
                    
                    ticker = yf.Ticker(symbol_pf)
                    hist = ticker.history(period='1d')
                    if not hist.empty:
                        current = hist['Close'].iloc[-1]
                    else:
                        current = 0
                    
                    exchange = get_exchange(symbol_pf)
                    currency = get_currency(symbol_pf)
                    
                    for pos in positions:
                        shares = pos['shares']
                        buy_price = pos['buy_price']
                        cost = shares * buy_price
                        value = shares * current
                        profit = value - cost
                        profit_pct = (profit / cost * 100) if cost > 0 else 0
                        
                        if currency == 'EUR':
                            total_cost_eur += cost
                            total_value_eur += value
                        
                        portfolio_data.append({
                            'Symbole': symbol_pf,
                            'Marché': exchange,
                            'Devise': currency,
                            'Actions': shares,
                            "Prix d'achat": format_currency(buy_price, symbol_pf),
                            'Prix actuel': format_currency(current, symbol_pf) if current > 0 else "N/A",
                            'Valeur': format_currency(value, symbol_pf) if value > 0 else "0",
                            'Profit': format_currency(profit, symbol_pf),
                            'Profit %': f"{profit_pct:.1f}%"
                        })
                except Exception as e:
                    st.warning(f"Impossible de charger {symbol_pf}")
            
            if portfolio_data:
                # Métriques globales en EUR
                total_profit_eur = total_value_eur - total_cost_eur
                total_profit_pct_eur = (total_profit_eur / total_cost_eur * 100) if total_cost_eur > 0 else 0
                
                col_e1, col_e2, col_e3 = st.columns(3)
                col_e1.metric("Valeur totale", f"€{total_value_eur:,.2f}")
                col_e2.metric("Coût total", f"€{total_cost_eur:,.2f}")
                col_e3.metric(
                    "Profit total",
                    f"€{total_profit_eur:,.2f}",
                    delta=f"{total_profit_pct_eur:.1f}%"
                )
                
                # Tableau des positions
                st.markdown("### 📋 Positions détaillées")
                df_portfolio = pd.DataFrame(portfolio_data)
                st.dataframe(df_portfolio, use_container_width=True)
                
                # Bouton pour vider le portefeuille
                if st.button("🗑️ Vider le portefeuille"):
                    st.session_state.portfolio = {}
                    st.rerun()
            else:
                st.info("Aucune donnée de performance disponible")
        else:
            st.info("Aucune position dans le portefeuille. Ajoutez des actions françaises pour commencer !")

# ============================================================================
# SECTIONS SUIVANTES (identiques à avant mais avec les corrections de symboles)
# ============================================================================
# ... (les autres sections restent identiques)

# ============================================================================
# WATCHLIST ET DERNIÈRE MISE À JOUR
# ============================================================================
st.markdown("---")
col_w1, col_w2 = st.columns([3, 1])

with col_w1:
    st.subheader("📋 Watchlist France - CAC 40")
    
    # Filtrer les symboles valides
    valid_watchlist = [s for s in st.session_state.watchlist if s not in DELISTED_STOCKS]
    
    # Afficher en grille
    cols_per_row = 4
    for i in range(0, len(valid_watchlist), cols_per_row):
        cols = st.columns(min(cols_per_row, len(valid_watchlist) - i))
        for j, sym in enumerate(valid_watchlist[i:i+cols_per_row]):
            with cols[j]:
                try:
                    ticker = yf.Ticker(sym)
                    hist = ticker.history(period='2d')
                    if not hist.empty and len(hist) >= 2:
                        price = hist['Close'].iloc[-1]
                        prev_close = hist['Close'].iloc[-2]
                        change = price - prev_close
                        change_pct = (change / prev_close * 100)
                        
                        # Nom simplifié
                        display_name = sym.replace('.PA', '')
                        
                        st.metric(
                            display_name,
                            f"€{price:.2f}",
                            delta=f"{change:.2f} ({change_pct:.1f}%)",
                            delta_color="normal" if change >= 0 else "inverse"
                        )
                    elif not hist.empty:
                        price = hist['Close'].iloc[-1]
                        st.metric(sym.replace('.PA', ''), f"€{price:.2f}")
                    else:
                        st.metric(sym.replace('.PA', ''), "N/A")
                except Exception as e:
                    st.metric(sym.replace('.PA', ''), "Err")

with col_w2:
    # Heures actuelles
    paris_time = datetime.now(PARIS_TZ)
    ny_time = datetime.now(NY_TZ)
    
    st.caption(f"🇫🇷 Paris: {paris_time.strftime('%H:%M:%S')}")
    st.caption(f"🇺🇸 NY: {ny_time.strftime('%H:%M:%S')}")
    
    # Statut des marchés
    market_status, market_icon = get_market_status()
    st.caption(f"{market_icon} Euronext: {market_status}")
    
    st.caption(f"Dernière MAJ: {paris_time.strftime('%H:%M:%S')}")
    
    if auto_refresh and hist is not None and not hist.empty:
        time.sleep(refresh_rate)
        st.rerun()

# Footer
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: gray; font-size: 0.8rem;'>"
    "🇫🇷 Tracker Bourse France - Euronext Paris | Données fournies par yfinance | "
    "⚠️ Données avec délai possible | 🕐 Heure de Paris (UTC+2)<br>"
    "🔄 Symboles mis à jour: ACA.PA → AC.PA | TOTF.PA → TTE.PA | FTE.PA → ORAN.PA | ❌ EDF.PA non coté"
    "</p>",
    unsafe_allow_html=True
)
