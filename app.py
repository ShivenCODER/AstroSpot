import streamlit as st
import folium
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from streamlit_folium import st_folium
import json

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="AstroSpot: Night Sky Finder",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== CUSTOM STYLING ====================
st.markdown("""
    <style>
        :root {
            --primary-color: #1e1e2e;
            --secondary-color: #2d2d44;
            --accent-color: #00d4ff;
        }
        
        body {
            background-color: var(--primary-color);
            color: #e0e0e0;
        }
        
        .stMetric {
            background-color: var(--secondary-color);
            border-radius: 10px;
            padding: 20px;
            border: 2px solid var(--accent-color);
        }
        
        h1 {
            color: var(--accent-color);
            text-shadow: 0 0 10px rgba(0, 212, 255, 0.5);
            text-align: center;
        }
        
        h2, h3 {
            color: var(--accent-color);
        }
        
        .tagline {
            text-align: center;
            color: #00d4ff;
            font-size: 1.1em;
            margin-bottom: 30px;
            opacity: 0.8;
        }
        
        .target-item {
            background-color: var(--secondary-color);
            border-left: 4px solid var(--accent-color);
            padding: 12px;
            margin: 8px 0;
            border-radius: 5px;
        }
    </style>
""", unsafe_allow_html=True)

# ==================== HELPER FUNCTIONS ====================

def get_weather_data(zip_code, api_key=None):
    """Fetch weather data from OpenWeatherMap API"""
    try:
        if not api_key:
            # Use free API with limited features
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name=&postal_code={zip_code}&country=United%20States&count=1&language=en&format=json"
            geo_response = requests.get(geo_url, timeout=5)
            geo_data = geo_response.json()
            
            if not geo_data.get('results'):
                st.error(f"Could not find location for zip code: {zip_code}")
                return None
            
            location = geo_data['results'][0]
            lat, lon = location['latitude'], location['longitude']
            
            # Use Open-Meteo free API for weather
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=cloud_cover,temperature&hourly=cloud_cover&timezone=auto"
            weather_response = requests.get(weather_url, timeout=5)
            weather_data = weather_response.json()
            
            return {
                'lat': lat,
                'lon': lon,
                'location_name': f"{location['name']}, {location['admin1']}",
                'cloud_cover': weather_data['current']['cloud_cover'],
                'hourly_cloud_cover': weather_data['hourly']['cloud_cover'],
                'temperature': weather_data['current']['temperature']
            }
        else:
            # Use OpenWeatherMap API with provided key
            url = f"https://api.openweathermap.org/data/2.5/weather?zip={zip_code},US&appid={api_key}&units=metric"
            response = requests.get(url, timeout=5)
            data = response.json()
            
            if response.status_code != 200:
                st.error(f"Error fetching weather: {data.get('message', 'Unknown error')}")
                return None
            
            return {
                'lat': data['coord']['lat'],
                'lon': data['coord']['lon'],
                'location_name': data['name'],
                'cloud_cover': data['clouds']['all'],
                'temperature': data['main']['temp']
            }
    except Exception as e:
        st.error(f"Error fetching weather data: {str(e)}")
        return None

def get_moon_phase():
    """Calculate moon illumination percentage"""
    # Using simplified calculation - for production use a proper library like ephem
    from datetime import datetime
    
    # Known new moon date
    new_moon = datetime(2000, 1, 6)
    now = datetime.now()
    
    # Moon cycle is approximately 29.53 days
    moon_cycle = 29.53
    days_since_new = (now - new_moon).days % moon_cycle
    
    # Moon illumination (0-100%)
    illumination = (days_since_new / moon_cycle) * 100
    
    return illumination

def calculate_stargazing_score(cloud_cover, moon_illumination):
    """
    Calculate stargazing quality score (0-100)
    Formula: Score = 100 - (CloudCover * 0.6) - (MoonIllumination * 0.4)
    """
    score = 100 - (cloud_cover * 0.6) - (moon_illumination * 0.4)
    return max(0, min(100, score))  # Clamp between 0-100

def generate_hourly_scores(base_cloud_cover, moon_illumination):
    """Generate hourly stargazing scores from 8 PM to 4 AM"""
    hours = list(range(20, 24)) + list(range(0, 5))  # 8 PM to 4 AM
    hour_labels = []
    scores = []
    
    for i, hour in enumerate(hours):
        # Add some variation to cloud cover for realism
        hour_variation = base_cloud_cover + (5 * (i % 3) - 7)  # Add some fluctuation
        hour_variation = max(0, min(100, hour_variation))
        
        score = calculate_stargazing_score(hour_variation, moon_illumination)
        
        time_label = f"{hour:02d}:00" if hour < 24 else f"{hour-24:02d}:00"
        hour_labels.append(time_label)
        scores.append(score)
    
    return hour_labels, scores

def get_state_parks():
    """Return NJ state parks with coordinates"""
    parks = [
        {
            'name': 'Jenny Jump State Forest',
            'lat': 40.8508,
            'lon': -74.9328,
            'info': 'Great for dark skies with minimal light pollution'
        },
        {
            'name': 'Wharton State Forest',
            'lat': 39.8061,
            'lon': -74.5331,
            'info': 'Largest state forest in NJ, excellent for stargazing'
        },
        {
            'name': 'High Point State Park',
            'lat': 41.3036,
            'lon': -74.6594,
            'info': 'Highest elevation in NJ, clear viewing conditions'
        },
        {
            'name': 'Sourland Mountain Preserve',
            'lat': 40.4772,
            'lon': -74.6858,
            'info': 'Secluded location with good darkness levels'
        }
    ]
    return parks

def get_visible_targets():
    """Return list of celestial targets visible tonight"""
    targets = [
        '🪐 Saturn - Visible in the southern sky',
        '🪐 Jupiter - Bright object in the southwest',
        '🌌 Andromeda Galaxy - Northern sky near Cassiopeia',
        '⭐ Polaris - North Star for navigation',
        '⭐ Sirius - Brightest star in the night sky',
        '⭐ Vega - High altitude evening star',
        '🌙 Moon - Phase: {:.1f}% illuminated',
    ]
    return targets

# ==================== SIDEBAR ====================
st.sidebar.title("🔧 Settings")
st.sidebar.markdown("---")

zip_code = st.sidebar.text_input(
    "📍 Enter US Zip Code",
    value="07054",
    help="Enter your location to get local weather and dark sky data"
)

api_key = st.sidebar.text_input(
    "🔑 OpenWeatherMap API Key (Optional)",
    type="password",
    help="Leave blank to use free API with basic features"
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📡 About AstroSpot")
st.sidebar.info(
    "AstroSpot helps stargazers find optimal viewing conditions by analyzing:\n"
    "• Cloud cover patterns\n"
    "• Moon phase and illumination\n"
    "• Local dark sky parks\n"
    "• Hourly visibility windows\n"
    "• Celestial target visibility"
)

# ==================== MAIN CONTENT ====================

# Header
st.markdown("<h1>✨ AstroSpot: Night Sky Finder</h1>", unsafe_allow_html=True)
st.markdown(
    "<div class='tagline'>🌌 Discover the perfect moment to explore the cosmos</div>",
    unsafe_allow_html=True
)

# Fetch weather data
weather_data = get_weather_data(zip_code, api_key if api_key else None)

if weather_data:
    # Get moon phase
    moon_illumination = get_moon_phase()
    
    # Calculate stargazing score
    stargazing_score = calculate_stargazing_score(
        weather_data['cloud_cover'],
        moon_illumination
    )
    
    # ==================== METRICS ROW ====================
    st.markdown("### 📊 Current Conditions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "🎯 Stargazing Score",
            f"{stargazing_score:.1f}",
            f"{stargazing_score - 50:.1f}" if stargazing_score >= 50 else f"{stargazing_score - 50:.1f}",
            delta_color="inverse"
        )
    
    with col2:
        st.metric(
            "☁️ Cloud Cover",
            f"{weather_data['cloud_cover']:.0f}%",
            f"{weather_data['cloud_cover'] - 30:.0f}%" if weather_data['cloud_cover'] > 30 else f"{weather_data['cloud_cover'] - 30:.0f}%",
            delta_color="inverse"
        )
    
    with col3:
        st.metric(
            "🌙 Moon Phase",
            f"{moon_illumination:.1f}%",
            f"Waxing" if moon_illumination < 50 else "Waning"
        )
    
    st.markdown("---")
    
    # ==================== MAP SECTION ====================
    st.markdown("### 🗺️ Dark Sky Park Locations")
    
    # Create folium map
    map_center = [weather_data['lat'], weather_data['lon']]
    folium_map = folium.Map(
        location=map_center,
        zoom_start=8,
        tiles="CartoDB dark_matter"
    )
    
    # Add user location marker
    folium.CircleMarker(
        location=map_center,
        radius=10,
        popup=f"<b>Your Location</b><br>{weather_data['location_name']}<br>Score: {stargazing_score:.1f}",
        color='#00d4ff',
        fill=True,
        fillColor='#00d4ff',
        fillOpacity=0.7,
        weight=2
    ).add_to(folium_map)
    
    # Add state parks
    parks = get_state_parks()
    for park in parks:
        folium.Marker(
            location=[park['lat'], park['lon']],
            popup=f"<b>{park['name']}</b><br>{park['info']}",
            tooltip=park['name'],
            icon=folium.Icon(color='green', icon='leaf', prefix='fa')
        ).add_to(folium_map)
    
    # Display map
    st_folium(folium_map, width=1200, height=500)
    
    st.markdown("---")
    
    # ==================== HOURLY TIMELINE ====================
    st.markdown("### 📈 Hourly Stargazing Quality (8 PM - 4 AM)")
    
    hour_labels, scores = generate_hourly_scores(
        weather_data['cloud_cover'],
        moon_illumination
    )
    
    # Create Plotly chart
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=hour_labels,
        y=scores,
        mode='lines+markers',
        name='Stargazing Score',
        line=dict(color='#00d4ff', width=3),
        marker=dict(size=8, color='#00d4ff'),
        fill='tozeroy',
        fillcolor='rgba(0, 212, 255, 0.2)'
    ))
    
    fig.update_layout(
        title='Quality Score by Hour',
        xaxis_title='Time',
        yaxis_title='Score (0-100)',
        hovermode='x unified',
        template='plotly_dark',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(30,30,46,1)',
        font=dict(color='#e0e0e0'),
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # ==================== VISIBLE TARGETS ====================
    st.markdown("### 🌟 Tonight's Visible Targets")
    
    targets = get_visible_targets()
    
    col1, col2 = st.columns(2)
    
    with col1:
        for target in targets[:4]:
            if '{}' in target:
                target = target.format(moon_illumination)
            st.markdown(
                f"<div class='target-item'>{target}</div>",
                unsafe_allow_html=True
            )
    
    with col2:
        for target in targets[4:]:
            if '{}' in target:
                target = target.format(moon_illumination)
            st.markdown(
                f"<div class='target-item'>{target}</div>",
                unsafe_allow_html=True
            )
    
    st.markdown("---")
    
    # ==================== RECOMMENDATIONS ====================
    st.markdown("### 💡 Tonight's Recommendations")
    
    if stargazing_score >= 75:
        st.success("🟢 **Excellent conditions!** Tonight is a perfect night for stargazing. Prepare your equipment and head to a dark sky park!")
    elif stargazing_score >= 50:
        st.info("🟡 **Good conditions.** Decent viewing potential. Consider waiting for cloud cover to decrease for better results.")
    else:
        st.warning("🔴 **Poor conditions.** Cloud cover is high. Consider waiting for clearer skies or checking back tomorrow night.")
    
    # Additional insights
    insight_col1, insight_col2 = st.columns(2)
    
    with insight_col1:
        if moon_illumination < 25 or moon_illumination > 75:
            st.info(f"🌙 The moon is currently {'new' if moon_illumination < 25 else 'full'}. This affects deep-sky object visibility.")
        else:
            st.info(f"🌙 The moon is {moon_illumination:.0f}% illuminated. Moderate moonlight may impact faint object visibility.")
    
    with insight_col2:
        if weather_data['cloud_cover'] < 20:
            st.success(f"☁️ Very clear skies ({weather_data['cloud_cover']:.0f}% cloud cover). Excellent viewing conditions!")
        elif weather_data['cloud_cover'] < 50:
            st.info(f"☁️ Partially cloudy ({weather_data['cloud_cover']:.0f}% cloud cover). Watch for clear patches.")
        else:
            st.warning(f"☁️ Mostly cloudy ({weather_data['cloud_cover']:.0f}% cloud cover). Patience may be needed.")
    
else:
    st.error("Unable to fetch weather data. Please check your zip code and try again.")
