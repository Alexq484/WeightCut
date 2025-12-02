import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import sqlite3

# Database setup
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)

class UserProfile(Base):
    __tablename__ = 'profiles'
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False)
    weight = Column(Float, nullable=False)
    target_weight = Column(Float, nullable=False)
    today_date = Column(Date, nullable=False)
    target_date = Column(Date, nullable=False)
    bodyfat_percentage = Column(Float)
    height = Column(Float, nullable=False)

class FoodLog(Base):
    __tablename__ = 'food_logs'
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False)
    log_date = Column(Date, nullable=False)
    food_name = Column(String, nullable=False)
    calories = Column(Float, nullable=False)
    protein = Column(Float, nullable=False)
    fat = Column(Float, nullable=False)
    carbs = Column(Float, nullable=False)
    fiber = Column(Float, default=0.0)
    sodium = Column(Float, default=0.0)
    meal_category = Column(String, default='Snacks')

class WeightLog(Base):
    __tablename__ = 'weight_logs'
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False)
    log_date = Column(Date, nullable=False, unique=False)
    weight = Column(Float, nullable=False)
    notes = Column(String, default="")

# Get database URL - supports both PostgreSQL (production) and SQLite (local dev)
def get_database_url():
    """Get database URL from Streamlit secrets or use local SQLite"""
    try:
        if 'DATABASE_URL' in st.secrets:
            # Production: Use PostgreSQL from Streamlit secrets
            return st.secrets['DATABASE_URL']
    except:
        pass
    
    # Local development: Use SQLite
    return 'sqlite:///weight_tracker.db'

# Create database engine for user data
DATABASE_URL = get_database_url()
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# Connect to food database
def get_food_db_connection():
    """Create connection to the food database"""
    return sqlite3.connect('food_nutrition.db')

def search_foods(search_term, limit=20):
    """Search for foods in the database, prioritizing foundation foods"""
    conn = get_food_db_connection()
    query = """
        SELECT fdc_id, description, data_type
        FROM food
        WHERE description LIKE ?
        ORDER BY 
            CASE 
                WHEN data_type = 'foundation_food' THEN 1
                ELSE 2
            END,
            description
        LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=(f'%{search_term}%', limit))
    conn.close()
    return df

def get_food_nutrients(fdc_id):
    """Get all nutrients for a specific food"""
    conn = get_food_db_connection()
    query = """
        SELECT 
            n.name as nutrient_name,
            fn.amount,
            n.unit_name
        FROM food_nutrient fn
        JOIN nutrient n ON fn.nutrient_id = n.id
        WHERE fn.fdc_id = ?
            AND fn.amount IS NOT NULL
        ORDER BY n.rank
    """
    df = pd.read_sql_query(query, conn, params=(fdc_id,))
    conn.close()
    return df

def get_food_macros(fdc_id):
    """Get macro nutrients (calories, protein, fat, carbs, fiber, sodium) for a food per 100g"""
    conn = get_food_db_connection()
    
    # Query for specific nutrient IDs we need
    # 1008 = Energy (calories), 1003 = Protein, 1004 = Fat
    # 1005 = Carbs, 1079 = Fiber, 1093 = Sodium
    query = """
        SELECT 
            fn.nutrient_id,
            fn.amount
        FROM food_nutrient fn
        WHERE fn.fdc_id = ?
            AND fn.nutrient_id IN (1008, 1003, 1004, 1005, 1079, 1093)
            AND fn.amount IS NOT NULL
    """
    
    df = pd.read_sql_query(query, conn, params=(fdc_id,))
    conn.close()
    
    # Map nutrient IDs to names
    nutrient_map = {
        1008: 'calories',
        1003: 'protein',
        1004: 'fat',
        1005: 'carbs',
        1079: 'fiber',
        1093: 'sodium'
    }
    
    # Initialize with zeros
    macros = {
        'calories': 0.0,
        'protein': 0.0,
        'fat': 0.0,
        'carbs': 0.0,
        'fiber': 0.0,
        'sodium': 0.0
    }
    
    # Fill in the values we have
    for _, row in df.iterrows():
        nutrient_id = row['nutrient_id']
        amount = row['amount']
        
        if nutrient_id in nutrient_map:
            macros[nutrient_map[nutrient_id]] = amount
    
    return macros


def calculate_macros(weight, target_calories, fat_percentage=0.25, carb_percentage=None, lean_body_mass=None):
    """
    Calculate macro breakdown based on weight and target calories.
    
    Args:
        weight: Body weight in pounds
        target_calories: Total daily calorie target
        fat_percentage: Percentage of total calories from fat (default 0.25 = 25%)
        carb_percentage: Percentage of total calories from carbs (optional, if None carbs fill remaining)
        lean_body_mass: Lean body mass in pounds (optional, used for protein calculation at 1.2g per lb)
    
    Returns:
        Dictionary with macro breakdown in grams and calories
    """
    # Use 1.2 * lean body mass for protein if available, otherwise use total weight
    if lean_body_mass:
        protein_grams = lean_body_mass * 1.2
    else:
        protein_grams = weight
    protein_calories = protein_grams * 4
    
    fat_calories = target_calories * fat_percentage
    fat_grams = fat_calories / 9
    
    if carb_percentage is not None:
        carb_calories = target_calories * carb_percentage
        carb_grams = carb_calories / 4
    else:
        # Carbs fill remaining calories
        carb_calories = target_calories - protein_calories - fat_calories
        carb_grams = carb_calories / 4
    
    return {
        'protein_grams': protein_grams,
        'protein_calories': protein_calories,
        'fat_grams': fat_grams,
        'fat_calories': fat_calories,
        'carb_grams': carb_grams,
        'carb_calories': carb_calories
    }

def calculate_micros(days_to_goal):
    """
    Calculate micronutrient targets based on days to goal.
    
    Args:
        days_to_goal: Number of days until target date
    
    Returns:
        Dictionary with fiber and sodium targets
    """
    if days_to_goal == 3:
        fiber_grams = 8
        sodium_mg = 1500
    elif days_to_goal == 2:
        fiber_grams = 5
        sodium_mg = 1000
    elif days_to_goal == 1:
        fiber_grams = 4
        sodium_mg = 800
    else:
        fiber_grams = 30  # Default
        sodium_mg = 2300
    
    return {
        'fiber_grams': fiber_grams,
        'sodium_mg': sodium_mg
    }

def adjust_calories_based_on_progress(base_calories, current_weight, target_weight, days_to_goal, session, username, current_date):
    """
    Adjust calorie targets based on actual weight progress vs target progression.
    Only adjusts when more than 3 days out from target.
    
    Args:
        base_calories: The baseline calorie calculation
        current_weight: Current weight in lbs
        target_weight: Target weight in lbs
        days_to_goal: Days until target date
        session: Database session to query weight logs
        username: Username to look up weight history
        current_date: Current date being viewed
    
    Returns:
        Adjusted calorie target and adjustment info dict
    """
    # Only adjust if more than 3 days out
    if days_to_goal <= 3:
        return base_calories, {
            'adjusted': False,
            'reason': 'Within 3 days of target - using standard protocol'
        }
    
    # Get most recent weight log
    latest_weight_log = session.query(WeightLog).filter_by(
        username=username
    ).filter(
        WeightLog.log_date <= current_date
    ).order_by(WeightLog.log_date.desc()).first()
    
    if not latest_weight_log:
        return base_calories, {
            'adjusted': False,
            'reason': 'No weight logged yet - log your weight to enable dynamic adjustments',
            'needs_weight_log': True
        }
    
    actual_weight = latest_weight_log.weight
    
    # Calculate where weight should be (5% above target when 3+ days out)
    target_weight_at_this_stage = target_weight * 1.05
    
    # Calculate difference from target progression
    weight_difference = actual_weight - target_weight_at_this_stage
    
    # Adjustment logic:
    # If more than 1 lb above target progression: reduce calories by 200
    # If more than 1 lb below target progression: increase calories by 200
    adjustment = 0
    adjustment_reason = ""
    
    if weight_difference > 1.0:
        # Too heavy - reduce calories
        adjustment = -200
        adjustment_reason = f"Weight {weight_difference:.1f} lbs above target progression ({actual_weight:.1f} vs {target_weight_at_this_stage:.1f} lbs)"
    elif weight_difference < -1.0:
        # Too light - increase calories
        adjustment = 200
        adjustment_reason = f"Weight {abs(weight_difference):.1f} lbs below target progression ({actual_weight:.1f} vs {target_weight_at_this_stage:.1f} lbs)"
    else:
        adjustment_reason = f"Weight on track ({actual_weight:.1f} vs target {target_weight_at_this_stage:.1f} lbs)"
    
    adjusted_calories = base_calories + adjustment
    
    return adjusted_calories, {
        'adjusted': adjustment != 0,
        'adjustment': adjustment,
        'reason': adjustment_reason,
        'actual_weight': actual_weight,
        'target_weight_at_stage': target_weight_at_this_stage,
        'difference': weight_difference
    }

def calculate_bmr_and_calories(weight, height, bodyfat_percentage):
    """
    Calculate BMR and adjust for body composition.
    Uses Katch-McArdle formula when body fat is provided, otherwise uses Mifflin-St Jeor.
    
    Args:
        weight: Body weight in pounds
        height: Height in inches
        bodyfat_percentage: Body fat percentage (0-100)
    
    Returns:
        BMR value
    """
    height_cm = height * 2.54
    weight_kg = weight * 0.453592
    
    if bodyfat_percentage and bodyfat_percentage > 0:
        # Katch-McArdle formula (more accurate when body composition is known)
        # BMR = 370 + (21.6 × lean body mass in kg)
        lean_body_mass_kg = weight_kg * (1 - bodyfat_percentage / 100)
        bmr = 370 + (21.6 * lean_body_mass_kg)
    else:
        # Mifflin-St Jeor formula (assuming male, age 30)
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * 30) + 5
    
    return bmr

# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = 'login'
if 'logged_in_user' not in st.session_state:
    st.session_state.logged_in_user = None
if 'current_date' not in st.session_state:
    st.session_state.current_date = datetime.today().date()
if 'selected_food' not in st.session_state:
    st.session_state.selected_food = None
if 'show_weight_form' not in st.session_state:
    st.session_state.show_weight_form = False
if 'selected_meal_category' not in st.session_state:
    st.session_state.selected_meal_category = 'Breakfast'
if 'editing_food_id' not in st.session_state:
    st.session_state.editing_food_id = None


def login_page():
    st.title("🏋️ Weight Tracker - Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        col1, col2 = st.columns(2)
        
        with col1:
            login_button = st.form_submit_button("Login")
        with col2:
            signup_button = st.form_submit_button("Sign Up")
        
        if login_button:
            session = Session()
            user = session.query(User).filter_by(username=username, password=password).first()
            session.close()
            
            if user:
                st.session_state.logged_in_user = username
                st.session_state.page = 'profile'
                st.rerun()
            else:
                st.error("Invalid username or password")
        
        if signup_button:
            if username and password:
                session = Session()
                existing_user = session.query(User).filter_by(username=username).first()
                
                if existing_user:
                    st.error("Username already exists")
                else:
                    new_user = User(username=username, password=password)
                    session.add(new_user)
                    session.commit()
                    st.success("Account created! Please login.")
                
                session.close()
            else:
                st.error("Please enter both username and password")

def profile_page():
    st.title(f"📊 Profile Setup - Welcome {st.session_state.logged_in_user}!")
    
    # Check if profile already exists
    session = Session()
    existing_profile = session.query(UserProfile).filter_by(
        username=st.session_state.logged_in_user
    ).first()
    session.close()
    
    # Pre-fill if profile exists
    default_weight = existing_profile.weight if existing_profile else 0.0
    default_target_weight = existing_profile.target_weight if existing_profile else 0.0
    default_height = existing_profile.height if existing_profile else 0.0
    default_bodyfat = existing_profile.bodyfat_percentage if existing_profile else 0.0
    default_target_date = existing_profile.target_date if existing_profile else datetime.today()
    
    col1, col2 = st.columns(2)
    
    with col1:
        weight = st.number_input(
            "Current Weight (lbs)", 
            min_value=0.0, 
            value=default_weight,
            step=0.1
        )
        target_weight = st.number_input(
            "Target Weight (lbs)", 
            min_value=0.0, 
            value=default_target_weight,
            step=0.1
        )
        height = st.number_input(
            "Height (inches)", 
            min_value=0.0, 
            value=default_height,
            step=0.1
        )
    
    with col2:
        today_date = st.date_input("Today's Date", value=datetime.today())
        target_date = st.date_input("Target Date", value=default_target_date)
        bodyfat_percentage = st.number_input(
            "Body Fat Percentage (%)", 
            min_value=0.0, 
            max_value=100.0,
            value=default_bodyfat,
            step=0.1,
            help="Used for more accurate calorie calculations via Katch-McArdle formula"
        )
    
    # Calculate and display macros dynamically (outside form)
    if weight > 0 and height > 0:
        st.subheader("📊 Your Macro Breakdown")
        
        # Calculate BMR using body fat if provided
        bmr = calculate_bmr_and_calories(weight, height, bodyfat_percentage)
        
        # Calculate lean body mass for protein calculation
        lean_body_mass = None
        if bodyfat_percentage and bodyfat_percentage > 0:
            lean_body_mass = weight * (1 - bodyfat_percentage / 100)
            st.info(f"💪 **Lean Body Mass:** {lean_body_mass:.1f} lbs → **Protein Target:** {lean_body_mass * 1.2:.1f}g (1.2g per lb LBM)")
        
        # Calculate deficit/surplus based on goal
        days_to_goal = (target_date - today_date).days
        weight_change = target_weight - weight

        # Determine activity level and macro split based on days to goal
        if days_to_goal == 3:  # Very active - training day
            base_calories = bmr * 1.725
            fat_pct = 0.25
        elif days_to_goal == 2:  # Moderately active
            base_calories = bmr * 1.55
            fat_pct = 0.35
        elif days_to_goal == 1:  # Lightly active - rest day
            base_calories = bmr * 1.375
            fat_pct = 0.45
        else:  # Default to moderate activity
            base_calories = bmr * 1.725
            fat_pct = 0.25
        
        # Adjust calories based on actual progress (only when >3 days out)
        session_temp = Session()
        target_calories, adjustment_info = adjust_calories_based_on_progress(
            base_calories, weight, target_weight, days_to_goal, 
            session_temp, st.session_state.logged_in_user, today_date
        )
        session_temp.close()
        
        # Calculate macros with adjusted calories
        macros = calculate_macros(weight, target_calories, fat_percentage=fat_pct, lean_body_mass=lean_body_mass)
        
        # Calculate micros
        micros = calculate_micros(days_to_goal)
        
        # Display BMR and formula used
        if bodyfat_percentage and bodyfat_percentage > 0:
            st.success(f"🔬 **BMR:** {int(bmr)} cal/day (Katch-McArdle formula - body composition adjusted)")
        else:
            st.info(f"🔬 **BMR:** {int(bmr)} cal/day (Mifflin-St Jeor formula - add body fat % for more accuracy)")
        
        # Show calorie adjustment info if applicable
        if adjustment_info.get('needs_weight_log'):
            st.info(f"ℹ️ **Dynamic Adjustments:** {adjustment_info['reason']}\n\nGo to Food Log → Log your weight to enable automatic calorie adjustments based on your progress!")
        elif adjustment_info['adjusted']:
            if adjustment_info['adjustment'] > 0:
                st.success(f"📈 **Calorie Adjustment:** +{adjustment_info['adjustment']} cal - {adjustment_info['reason']}")
            else:
                st.warning(f"📉 **Calorie Adjustment:** {adjustment_info['adjustment']} cal - {adjustment_info['reason']}")
        else:
            if days_to_goal > 3:
                st.info(f"✅ **Weight Progress:** {adjustment_info['reason']}")
            else:
                st.info(f"🎯 **Final Days Protocol:** {adjustment_info['reason']}")
        
        # Display macros
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Calories", f"{int(target_calories)}")
        with col2:
            st.metric("Protein", f"{int(macros['protein_grams'])}g")
        with col3:
            st.metric("Fat", f"{int(macros['fat_grams'])}g")
        with col4:
            st.metric("Carbs", f"{int(macros['carb_grams'])}g")
        
        # Display micros
        st.subheader("🔬 Your Micro Targets")
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Fiber", f"{micros['fiber_grams']}g")
        with col2:
            st.metric("Sodium", f"{micros['sodium_mg']}mg")
        
        # Display summary
        st.subheader("Profile Summary")
        df = pd.DataFrame({
            'Metric': ['Current Weight', 'Target Weight', 'Height', 'Body Fat %', 'Target Date', 'Days to Goal'],
            'Value': [
                f"{weight} lbs",
                f"{target_weight} lbs",
                f"{height} inches",
                f"{bodyfat_percentage}%" if bodyfat_percentage > 0 else "Not provided",
                target_date.strftime('%Y-%m-%d'),
                f"{days_to_goal} days"
            ]
        })
        st.dataframe(df, hide_index=True)
        
        # Macro breakdown chart
        macro_df = pd.DataFrame({
            'Macro': ['Protein', 'Fat', 'Carbs'],
            'Grams': [int(macros['protein_grams']), int(macros['fat_grams']), int(macros['carb_grams'])],
            'Calories': [int(macros['protein_calories']), int(macros['fat_calories']), int(macros['carb_calories'])]
        })
        st.subheader("Macro Details")
        st.dataframe(macro_df, hide_index=True)
    
    with st.form("profile_form"):
        st.write("### Save Your Profile")
        
        col1, col2 = st.columns(2)
        with col1:
            submit_button = st.form_submit_button("Save Profile")
        with col2:
            logout_button = st.form_submit_button("Logout")
        
        if submit_button:
            session = Session()
            
            # Delete existing profile if it exists
            session.query(UserProfile).filter_by(
                username=st.session_state.logged_in_user
            ).delete()
            
            # Create new profile
            new_profile = UserProfile(
                username=st.session_state.logged_in_user,
                weight=weight,
                target_weight=target_weight,
                today_date=today_date,
                target_date=target_date,
                bodyfat_percentage=bodyfat_percentage,
                height=height
            )
            session.add(new_profile)
            session.commit()
            session.close()
            
            st.success("✅ Profile saved successfully!")
        
        if logout_button:
            st.session_state.logged_in_user = None
            st.session_state.page = 'login'
            st.rerun()
    
    # Button to navigate to food log
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📝 Go to Food Log"):
            st.session_state.page = 'food_log'
            st.rerun()
    with col2:
        if st.button("📈 View Progress"):
            st.session_state.page = 'progress'
            st.rerun()

def food_log_page():
    st.title(f"🍽️ Food Log - {st.session_state.logged_in_user}")
    
    # Navigation
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("← Back to Profile"):
            st.session_state.page = 'profile'
            st.rerun()
    with col2:
        if st.button("📈 Progress"):
            st.session_state.page = 'progress'
            st.rerun()
    with col3:
        st.write(f"**Date:** {st.session_state.current_date}")
    with col4:
        if st.button("Logout"):
            st.session_state.logged_in_user = None
            st.session_state.page = 'login'
            st.rerun()
    
    # Multi-day navigation for past days
    st.divider()
    st.subheader("📅 Date Navigation")
    
    col1, col2, col3, col4 = st.columns([1, 2, 2, 1])
    
    with col1:
        # Previous day button
        if st.button("◀ Previous", use_container_width=True):
            st.session_state.current_date = st.session_state.current_date - timedelta(days=1)
            st.session_state.show_weight_form = False
            st.rerun()
    
    with col2:
        # Date picker for past days only
        max_date = datetime.today().date()
        selected_date = st.date_input(
            "Select Date",
            value=st.session_state.current_date,
            max_value=max_date,
            key="date_picker"
        )
        
        # Update current_date if changed
        if selected_date != st.session_state.current_date:
            st.session_state.current_date = selected_date
            st.session_state.show_weight_form = False
            st.rerun()
    
    with col3:
        # Show days from today
        days_ago = (datetime.today().date() - st.session_state.current_date).days
        if days_ago == 0:
            date_label = "📍 Today"
        elif days_ago == 1:
            date_label = "📅 Yesterday"
        else:
            date_label = f"📅 {days_ago} days ago"
        
        st.info(date_label)
    
    with col4:
        # Next day button (only show if not viewing today)
        today = datetime.today().date()
        if st.session_state.current_date < today:
            if st.button("Next ▶", use_container_width=True):
                st.session_state.current_date = st.session_state.current_date + timedelta(days=1)
                st.session_state.show_weight_form = False
                st.rerun()
        else:
            st.button("Today", disabled=True, use_container_width=True)
    
    st.divider()
    
    # Get user profile for targets
    session = Session()
    profile = session.query(UserProfile).filter_by(
        username=st.session_state.logged_in_user
    ).first()
    
    if not profile:
        st.warning("Please complete your profile first!")
        session.close()
        return
    
    # Weight tracking section - date aware title
    today = datetime.today().date()
    if st.session_state.current_date == today:
        st.subheader("⚖️ Today's Weight")
    else:
        days_ago = (today - st.session_state.current_date).days
        if days_ago == 1:
            st.subheader("⚖️ Yesterday's Weight")
        else:
            st.subheader(f"⚖️ Weight on {st.session_state.current_date.strftime('%B %d, %Y')}")
    
    # Check if weight already logged for this date
    existing_weight_log = session.query(WeightLog).filter_by(
        username=st.session_state.logged_in_user,
        log_date=st.session_state.current_date
    ).first()
    
    # Show weight info and buttons when form is NOT showing
    if existing_weight_log and not st.session_state.show_weight_form:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.success(f"✅ Weight logged: **{existing_weight_log.weight} lbs**")
            if existing_weight_log.notes:
                st.info(f"Note: {existing_weight_log.notes}")
        with col2:
            if st.button("Update Weight"):
                st.session_state.show_weight_form = True
                st.rerun()
    elif not existing_weight_log and not st.session_state.show_weight_form:
        if st.session_state.current_date == datetime.today().date():
            st.info("⚠️ No weight logged for today")
            button_text = "Log Today's Weight"
        else:
            st.info(f"⚠️ No weight logged for {st.session_state.current_date.strftime('%B %d, %Y')}")
            button_text = "Log Weight for This Day"
        
        if st.button(button_text):
            st.session_state.show_weight_form = True
            st.rerun()
    
    # Weight entry form - shows when flag is True
    if st.session_state.show_weight_form:
        with st.form("weight_log_form"):
            st.write("### Log Your Weight")
            col1, col2 = st.columns(2)
            with col1:
                current_weight = st.number_input(
                    "Weight (lbs)", 
                    min_value=0.0,
                    value=existing_weight_log.weight if existing_weight_log else profile.weight,
                    step=0.1
                )
            with col2:
                weight_notes = st.text_input(
                    "Notes (optional)",
                    value=existing_weight_log.notes if existing_weight_log else "",
                    placeholder="e.g., morning, after workout"
                )
            
            col1, col2 = st.columns(2)
            with col1:
                save_weight = st.form_submit_button("Save Weight", type="primary")
            with col2:
                cancel_weight = st.form_submit_button("Cancel")
            
            if save_weight:
                if existing_weight_log:
                    # Update existing log
                    existing_weight_log.weight = current_weight
                    existing_weight_log.notes = weight_notes
                else:
                    # Create new log
                    new_weight_log = WeightLog(
                        username=st.session_state.logged_in_user,
                        log_date=st.session_state.current_date,
                        weight=current_weight,
                        notes=weight_notes
                    )
                    session.add(new_weight_log)
                
                session.commit()
                st.session_state.show_weight_form = False
                st.success(f"✅ Weight saved: {current_weight} lbs")
                st.rerun()
            
            if cancel_weight:
                st.session_state.show_weight_form = False
                st.rerun()
    
    st.divider()
    
    # Calculate targets using body composition
    bmr = calculate_bmr_and_calories(profile.weight, profile.height, profile.bodyfat_percentage)
    
    # Calculate lean body mass for protein
    lean_body_mass = None
    if profile.bodyfat_percentage and profile.bodyfat_percentage > 0:
        lean_body_mass = profile.weight * (1 - profile.bodyfat_percentage / 100)
    
    days_to_goal = (profile.target_date - st.session_state.current_date).days
    
    # Determine base calories and fat percentage
    if days_to_goal == 3:
        base_calories = bmr * 1.725
        fat_pct = 0.25
    elif days_to_goal == 2:
        base_calories = bmr * 1.55
        fat_pct = 0.35
    elif days_to_goal == 1:
        base_calories = bmr * 1.375
        fat_pct = 0.45
    else:
        base_calories = bmr * 1.725
        fat_pct = 0.25
    
    # Adjust calories based on actual progress (only when >3 days out)
    target_calories, adjustment_info = adjust_calories_based_on_progress(
        base_calories, profile.weight, profile.target_weight, days_to_goal,
        session, st.session_state.logged_in_user, st.session_state.current_date
    )
    
    # Calculate macros with adjusted calories
    macros = calculate_macros(profile.weight, target_calories, fat_percentage=fat_pct, lean_body_mass=lean_body_mass)
    
    micros = calculate_micros(days_to_goal)
    
    # Get food logs for selected date
    food_logs = session.query(FoodLog).filter_by(
        username=st.session_state.logged_in_user,
        log_date=st.session_state.current_date
    ).all()
    
    # Calculate totals overall and by meal
    meal_categories = ['Breakfast', 'Lunch', 'Dinner', 'Snacks']
    meal_totals = {}
    
    for category in meal_categories:
        category_logs = [log for log in food_logs if getattr(log, 'meal_category', 'Snacks') == category]
        meal_totals[category] = {
            'calories': sum(log.calories for log in category_logs),
            'protein': sum(log.protein for log in category_logs),
            'fat': sum(log.fat for log in category_logs),
            'carbs': sum(log.carbs for log in category_logs),
            'fiber': sum(log.fiber for log in category_logs),
            'sodium': sum(log.sodium for log in category_logs),
            'count': len(category_logs)
        }
    
    # Calculate overall totals
    total_calories = sum(log.calories for log in food_logs)
    total_protein = sum(log.protein for log in food_logs)
    total_fat = sum(log.fat for log in food_logs)
    total_carbs = sum(log.carbs for log in food_logs)
    total_fiber = sum(log.fiber for log in food_logs)
    total_sodium = sum(log.sodium for log in food_logs)
    
    # Display targets vs actual
    if st.session_state.current_date == datetime.today().date():
        st.subheader("📊 Today's Progress")
    else:
        st.subheader(f"📊 Progress for {st.session_state.current_date.strftime('%B %d, %Y')}")
    
    # Show calorie adjustment info if applicable
    if adjustment_info.get('needs_weight_log'):
        st.warning(f"⚠️ **Dynamic Adjustments Disabled:** {adjustment_info['reason']}\n\nLog your weight above to see automatic calorie adjustments!")
    elif adjustment_info['adjusted']:
        if adjustment_info['adjustment'] > 0:
            st.success(f"📈 **Calorie Adjustment:** +{adjustment_info['adjustment']} cal/day - {adjustment_info['reason']}")
        else:
            st.warning(f"📉 **Calorie Adjustment:** {adjustment_info['adjustment']} cal/day - {adjustment_info['reason']}")
    elif days_to_goal > 3:
        st.info(f"✅ {adjustment_info['reason']}")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Calories",
            f"{int(total_calories)}/{int(target_calories)}",
            delta=f"{int(target_calories - total_calories)}"
        )
    with col2:
        st.metric(
            "Protein",
            f"{int(total_protein)}/{int(macros['protein_grams'])}g",
            delta=f"{int(macros['protein_grams'] - total_protein)}g"
        )
    with col3:
        st.metric(
            "Fat",
            f"{int(total_fat)}/{int(macros['fat_grams'])}g",
            delta=f"{int(macros['fat_grams'] - total_fat)}g"
        )
    with col4:
        st.metric(
            "Carbs",
            f"{int(total_carbs)}/{int(macros['carb_grams'])}g",
            delta=f"{int(macros['carb_grams'] - total_carbs)}g"
        )
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            "Fiber",
            f"{int(total_fiber)}/{micros['fiber_grams']}g",
            delta=f"{int(micros['fiber_grams'] - total_fiber)}g"
        )
    with col2:
        st.metric(
            "Sodium",
            f"{int(total_sodium)}/{micros['sodium_mg']}mg",
            delta=f"{int(micros['sodium_mg'] - total_sodium)}mg"
        )
    
    # Display meal breakdown
    st.divider()
    st.subheader("🍽️ Meal Breakdown")
    
    # Create tabs for each meal
    tab1, tab2, tab3, tab4 = st.tabs(["🌅 Breakfast", "☀️ Lunch", "🌙 Dinner", "🍿 Snacks"])
    
    tabs = [tab1, tab2, tab3, tab4]
    emojis = ['🌅', '☀️', '🌙', '🍿']
    
    for idx, (category, tab) in enumerate(zip(meal_categories, tabs)):
        with tab:
            totals = meal_totals[category]
            
            if totals['count'] > 0:
                col1, col2, col3, col4, col5, col6 = st.columns(6)
                with col1:
                    st.metric("Calories", f"{int(totals['calories'])}")
                with col2:
                    st.metric("Protein", f"{int(totals['protein'])}g")
                with col3:
                    st.metric("Fat", f"{int(totals['fat'])}g")
                with col4:
                    st.metric("Carbs", f"{int(totals['carbs'])}g")
                with col5:
                    st.metric("Fiber", f"{int(totals['fiber'])}g")
                with col6:
                    st.metric("Sodium", f"{int(totals['sodium'])}mg")
                
                st.write("---")
                
                # Show foods for this meal
                category_foods = [log for log in food_logs if getattr(log, 'meal_category', 'Snacks') == category]
                food_data = []
                for log in category_foods:
                    food_data.append({
                        'Food': log.food_name,
                        'Calories': int(log.calories),
                        'Protein': f"{log.protein:.1f}g",
                        'Fat': f"{log.fat:.1f}g",
                        'Carbs': f"{log.carbs:.1f}g",
                        'Fiber': f"{log.fiber:.1f}g",
                        'Sodium': f"{int(log.sodium)}mg",
                        'ID': log.id
                    })
                
                if food_data:
                    df = pd.DataFrame(food_data)
                    st.dataframe(df.drop('ID', axis=1), hide_index=True, use_container_width=True)
            else:
                st.info(f"No foods logged for {category.lower()} yet.")
    
    # Copy Past Meals section
    st.divider()
    st.subheader("📋 Copy Past Meals")
    
    # Get unique past meals (from last 30 days, excluding today)
    past_date_limit = st.session_state.current_date - timedelta(days=30)
    past_food_logs = session.query(FoodLog).filter(
        FoodLog.username == st.session_state.logged_in_user,
        FoodLog.log_date >= past_date_limit,
        FoodLog.log_date < st.session_state.current_date
    ).order_by(FoodLog.log_date.desc()).all()
    
    if past_food_logs:
        # Group by date and meal category
        meals_by_date = {}
        for log in past_food_logs:
            date_key = log.log_date.strftime('%Y-%m-%d')
            meal_cat = getattr(log, 'meal_category', 'Snacks')
            
            if date_key not in meals_by_date:
                meals_by_date[date_key] = {}
            if meal_cat not in meals_by_date[date_key]:
                meals_by_date[date_key][meal_cat] = []
            
            meals_by_date[date_key][meal_cat].append(log)
        
        # Create options for selectbox
        meal_options = []
        meal_data = {}
        
        for date_str, categories in meals_by_date.items():
            for category, logs in categories.items():
                total_cals = sum(log.calories for log in logs)
                foods_list = ", ".join([log.food_name for log in logs[:3]])  # Show first 3 foods
                if len(logs) > 3:
                    foods_list += f" (+{len(logs)-3} more)"
                
                option_label = f"{date_str} - {category} ({len(logs)} items, {int(total_cals)} cal) - {foods_list}"
                meal_options.append(option_label)
                meal_data[option_label] = {
                    'date': date_str,
                    'category': category,
                    'logs': logs
                }
        
        selected_past_meal = st.selectbox(
            "Select a past meal to copy:",
            options=["-- Select a past meal --"] + meal_options,
            key="past_meal_selector"
        )
        
        if selected_past_meal != "-- Select a past meal --":
            meal_info = meal_data[selected_past_meal]
            
            # Show meal details
            with st.expander("📖 View Meal Details", expanded=True):
                st.write(f"**From:** {meal_info['date']} - {meal_info['category']}")
                st.write(f"**Items in this meal:**")
                
                meal_details = []
                for log in meal_info['logs']:
                    meal_details.append({
                        'Food': log.food_name,
                        'Calories': int(log.calories),
                        'Protein': f"{log.protein:.1f}g",
                        'Fat': f"{log.fat:.1f}g",
                        'Carbs': f"{log.carbs:.1f}g"
                    })
                
                df = pd.DataFrame(meal_details)
                st.dataframe(df, hide_index=True, use_container_width=True)
                
                # Totals
                total_cals = sum(log.calories for log in meal_info['logs'])
                total_prot = sum(log.protein for log in meal_info['logs'])
                total_fat = sum(log.fat for log in meal_info['logs'])
                total_carbs = sum(log.carbs for log in meal_info['logs'])
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Calories", int(total_cals))
                with col2:
                    st.metric("Total Protein", f"{total_prot:.1f}g")
                with col3:
                    st.metric("Total Fat", f"{total_fat:.1f}g")
                with col4:
                    st.metric("Total Carbs", f"{total_carbs:.1f}g")
            
            # Option to copy to a different meal category
            st.write("**Copy to:**")
            target_category = st.radio(
                "Select target meal category:",
                meal_categories,
                horizontal=True,
                key="target_meal_category"
            )
            
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("📋 Copy This Meal", type="primary", use_container_width=True):
                    # Copy all foods from this meal to current date
                    for log in meal_info['logs']:
                        new_log = FoodLog(
                            username=st.session_state.logged_in_user,
                            log_date=st.session_state.current_date,
                            food_name=log.food_name,
                            calories=log.calories,
                            protein=log.protein,
                            fat=log.fat,
                            carbs=log.carbs,
                            fiber=log.fiber,
                            sodium=log.sodium,
                            meal_category=target_category
                        )
                        session.add(new_log)
                    
                    session.commit()
                    st.success(f"✅ Copied {len(meal_info['logs'])} items to {target_category}!")
                    st.rerun()
            
            with col2:
                st.info("💡 This will copy all foods from the selected meal to your current date.")
    else:
        st.info("No past meals found in the last 30 days. Start logging meals to use this feature!")
    
    # Food database search section
    st.divider()
    st.subheader("🔍 Add Food")
    
    # Meal category selector
    selected_category = st.radio(
        "Select meal:",
        meal_categories,
        horizontal=True,
        key="meal_category_selector"
    )
    st.session_state.selected_meal_category = selected_category
    
    # Low fiber/sodium reference
    with st.expander("📋 Quick Reference: Low Fiber & Low Sodium Foods"):
        st.markdown("""
        **Best options for cutting weight before weigh-in:**
        
        ### 🥩 Meats (0g fiber)
        **Beef:**
        - **Beef, round, eye of round** - 122 cal, 23.4g protein, 50mg sodium
        - **Beef, porterhouse steak** - 145 cal, 22.7g protein, 43mg sodium
        - **Beef, top loin steak** - 155 cal, 22.8g protein, 45mg sodium
        - **Beef, tenderloin roast** - 176 cal, 27.7g protein, 54mg sodium
        - **Beef, t-bone steak** - 219 cal, 27.3g protein, 67mg sodium
        - **Beef, top round roast** - Available in database
        - **Frankfurter, beef, unheated** - Available in database
        
        **Chicken:**
        - **Chicken, breast** (skinless, boneless, cooked, braised)
        - **Chicken, drumstick** (meat only, cooked, braised)
        
        **Pork:**
        - **Pork, bacon** (cooked, restaurant)
        - **Sausage, Italian, pork, mild** (cooked, pan-fried)
        - **Sausage, pork, chorizo** (link or ground, cooked, pan-fried)
        - **Restaurant, Chinese, sweet and sour pork**
        - **Restaurant, Latino, tamale, pork**
        
        **Turkey:**
        - **Turkey, ground** (93% lean, 7% fat, pan-broiled crumbles)
        - **Sausage, turkey, breakfast links, mild, raw**
        
        **Ham:**
        - **Ham, sliced, pre-packaged** (deli meat, 96% fat free, water added)
        
        **Other Sausages:**
        - **Sausage, breakfast sausage, beef** (pre-cooked, unprepared)
        
        ### 🍞 Grains & Breads
        **Breads:**
        - **Bread, white, commercially prepared**
        
        **Flours:**
        - **Rice flour, white** - 359 cal, 0.5g fiber, 5mg sodium
        - **Flour, bread, white** (enriched, unbleached)
        
        **Other Grains:**
        - **Restaurant, Chinese, fried rice, without meat**
        
        ### 🍇 Fruits (Low fiber: 0.2-2g)
        - **Grapefruit juice** - 37 cal, 0.2g fiber, 1mg sodium
        - **Cantaloupe** - 34 cal, 0.8g fiber, 30mg sodium
        - **Bananas** - 97 cal, 1.7g fiber, 0mg sodium
        - **Apples (Honeycrisp)** - 60 cal, 1.7g fiber, 0mg sodium
        - **Peaches** - 42 cal, 1.5g fiber, 13mg sodium
        - **Nectarines** - 39 cal, 1.5g fiber, 13mg sodium
        - **Strawberries** - 31 cal, 1.8g fiber, 10mg sodium
        - **Oranges** - 47 cal, 2.0g fiber, 9mg sodium
        
        ### 🥛 Dairy
        - **Greek yogurt, strawberry, nonfat** - 83 cal, 8.1g protein, 0.6g fiber, 32mg sodium
        
        ### 🍚 Other
        - **Onions, white** - 35 cal, 1.2g fiber, 2mg sodium
        
        💡 *All nutrition values per 100g unless otherwise noted. All beef and meat options have 0g fiber!*
        💡 *Search the database for any of these items to get complete nutritional information.*
        """)
    
    st.write("")  # Add some spacing
    
    search_term = st.text_input("Search for a food:", placeholder="e.g., chicken, apple, rice")
    
    if search_term:
        with st.spinner("Searching..."):
            search_results = search_foods(search_term)
            
            if not search_results.empty:
                st.write(f"Found {len(search_results)} results:")
                
                # Create a selectbox for food selection
                food_options = {
                    f"{row['description']} ({row['data_type']})": {
                        'fdc_id': row['fdc_id'],
                        'description': row['description']
                    }
                    for idx, row in search_results.iterrows()
                }
                
                selected_food_key = st.selectbox(
                    "Select a food:",
                    options=["-- Select --"] + list(food_options.keys()),
                    key="food_selector"
                )
                
                if selected_food_key != "-- Select --":
                    if st.button("Add This Food", type="primary"):
                        st.session_state.selected_food = food_options[selected_food_key]
                        st.rerun()
            else:
                st.info("No foods found. Try a different search term.")
    
    # Display selected food details and add form
    if st.session_state.selected_food:
        st.divider()
        st.subheader(f"➕ Add: {st.session_state.selected_food['description']}")
        
        with st.spinner("Loading nutritional information..."):
            macros_data = get_food_macros(st.session_state.selected_food['fdc_id'])
            nutrients_data = get_food_nutrients(st.session_state.selected_food['fdc_id'])
        
        # Check if food has any nutritional data
        has_data = macros_data['calories'] > 0 or macros_data['protein'] > 0 or macros_data['fat'] > 0 or macros_data['carbs'] > 0
        
        if not has_data:
            st.warning("""
                ⚠️ **No nutritional data available for this food.**
                
                This food item doesn't have nutrient information in the database. 
                Try searching for a similar food or use manual entry below.
                
                💡 Tip: Foods marked as "foundation_food" usually have complete nutrition data.
            """)
            
            if st.button("Clear Selection"):
                st.session_state.selected_food = None
                st.rerun()
        else:
            # Display macro summary (per 100g)
            st.info("📏 **Nutrition values shown per 100g**")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Calories", f"{macros_data['calories']:.0f}")
            with col2:
                st.metric("Protein", f"{macros_data['protein']:.1f}g")
            with col3:
                st.metric("Fat", f"{macros_data['fat']:.1f}g")
            with col4:
                st.metric("Carbs", f"{macros_data['carbs']:.1f}g")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Fiber", f"{macros_data['fiber']:.1f}g")
            with col2:
                st.metric("Sodium", f"{macros_data['sodium']:.0f}mg")
            
            # Show expandable full nutrient details
            with st.expander("📋 View All Nutrients"):
                if not nutrients_data.empty:
                    st.dataframe(nutrients_data, hide_index=True, use_container_width=True)
                else:
                    st.info("No detailed nutrient data available")
            
            # Add to log form
            with st.form("add_from_database"):
                st.write("**Enter amount in grams:**")
                grams = st.number_input(
                    "Grams", 
                    min_value=1.0, 
                    value=100.0, 
                    step=10.0,
                    help="All nutrition values are per 100g. Enter the amount you consumed."
                )
                
                # Show calculated values for the specified grams
                multiplier = grams / 100.0
                st.write("**Calculated nutrition for your portion:**")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.write(f"Calories: {macros_data['calories'] * multiplier:.0f}")
                with col2:
                    st.write(f"Protein: {macros_data['protein'] * multiplier:.1f}g")
                with col3:
                    st.write(f"Fat: {macros_data['fat'] * multiplier:.1f}g")
                with col4:
                    st.write(f"Carbs: {macros_data['carbs'] * multiplier:.1f}g")
                
                col1, col2 = st.columns(2)
                with col1:
                    add_button = st.form_submit_button("Add to Log", type="primary")
                with col2:
                    cancel_button = st.form_submit_button("Cancel")
                
                if add_button:
                    new_log = FoodLog(
                        username=st.session_state.logged_in_user,
                        log_date=st.session_state.current_date,
                        food_name=st.session_state.selected_food['description'],
                        calories=macros_data['calories'] * multiplier,
                        protein=macros_data['protein'] * multiplier,
                        fat=macros_data['fat'] * multiplier,
                        carbs=macros_data['carbs'] * multiplier,
                        fiber=macros_data['fiber'] * multiplier,
                        sodium=macros_data['sodium'] * multiplier,
                        meal_category=st.session_state.selected_meal_category
                    )
                    session.add(new_log)
                    session.commit()
                    st.success(f"Added {grams}g of {st.session_state.selected_food['description']} to {st.session_state.selected_meal_category}!")
                    st.session_state.selected_food = None
                    st.rerun()
                
                if cancel_button:
                    st.session_state.selected_food = None
                    st.rerun()
    
    # Manual entry section
    st.divider()
    st.subheader("✏️ Manual Entry")
    with st.form("add_food_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            food_name = st.text_input("Food Name")
            manual_calories = st.number_input("Calories (optional - leave 0 to auto-calculate)", min_value=0.0, step=1.0, key="manual_calories")
            protein = st.number_input("Protein (g)", min_value=0.0, step=0.1, key="manual_protein")
            fat = st.number_input("Fat (g)", min_value=0.0, step=0.1, key="manual_fat")
        
        with col2:
            carbs = st.number_input("Carbs (g)", min_value=0.0, step=0.1, key="manual_carbs")
            fiber = st.number_input("Fiber (g)", min_value=0.0, step=0.1, key="manual_fiber")
            sodium = st.number_input("Sodium (mg)", min_value=0.0, step=1.0, key="manual_sodium")
        
        # Calculate calories from macros (Protein: 4 cal/g, Fat: 9 cal/g, Carbs: 4 cal/g)
        calculated_calories = (protein * 4) + (fat * 9) + (carbs * 4)
        
        # Use manual calories if provided, otherwise use calculated
        final_calories = manual_calories if manual_calories > 0 else calculated_calories
        
        # Display calorie information
        if manual_calories > 0:
            st.info(f"**Using Manual Calories:** {manual_calories:.1f} kcal")
        else:
            st.info(f"**Auto-Calculated Calories:** {calculated_calories:.1f} kcal (P: {protein*4:.0f} + F: {fat*9:.0f} + C: {carbs*4:.0f})")
        
        # Create two columns for buttons
        button_col1, button_col2 = st.columns(2)
        
        with button_col1:
            submit_button = st.form_submit_button("Add Manually", type="primary")
        with button_col2:
            clear_button = st.form_submit_button("Clear", type="secondary")
        
        if clear_button:
            st.rerun()
        
        if submit_button:
            if food_name:
                new_log = FoodLog(
                    username=st.session_state.logged_in_user,
                    log_date=st.session_state.current_date,
                    food_name=food_name,
                    calories=final_calories,
                    protein=protein,
                    fat=fat,
                    carbs=carbs,
                    fiber=fiber,
                    sodium=sodium,
                    meal_category=st.session_state.selected_meal_category
                )
                session.add(new_log)
                session.commit()
                st.success(f"Added {food_name} to {st.session_state.selected_meal_category}!")
                st.rerun()
            else:
                st.error("Please enter a food name")
    
    # Edit food section
    if food_logs:
        st.divider()
        st.subheader("✏️ Edit Food")
        
        # Select food to edit
        food_to_edit = st.selectbox(
            "Select food to edit",
            options=[f"{log.food_name} ({getattr(log, 'meal_category', 'Snacks')}) - {log.calories:.0f} cal - ID: {log.id}" for log in food_logs],
            key="edit_selectbox"
        )
        
        if food_to_edit:
            edit_food_id = int(food_to_edit.split("ID: ")[1])
            
            # Get the selected food log
            food_to_edit_obj = session.query(FoodLog).filter_by(id=edit_food_id).first()
            
            if food_to_edit_obj:
                st.write(f"**Editing:** {food_to_edit_obj.food_name}")
                
                with st.form(f"edit_food_form_{edit_food_id}"):
                    edit_col1, edit_col2 = st.columns(2)
                    
                    with edit_col1:
                        edit_food_name = st.text_input("Food Name", value=food_to_edit_obj.food_name, key=f"edit_name_{edit_food_id}")
                        edit_manual_calories = st.number_input("Calories (optional - leave 0 to auto-calculate)", min_value=0.0, step=1.0, value=food_to_edit_obj.calories, key=f"edit_cal_{edit_food_id}")
                        edit_protein = st.number_input("Protein (g)", min_value=0.0, step=0.1, value=food_to_edit_obj.protein, key=f"edit_protein_{edit_food_id}")
                        edit_fat = st.number_input("Fat (g)", min_value=0.0, step=0.1, value=food_to_edit_obj.fat, key=f"edit_fat_{edit_food_id}")
                    
                    with edit_col2:
                        edit_carbs = st.number_input("Carbs (g)", min_value=0.0, step=0.1, value=food_to_edit_obj.carbs, key=f"edit_carbs_{edit_food_id}")
                        edit_fiber = st.number_input("Fiber (g)", min_value=0.0, step=0.1, value=food_to_edit_obj.fiber, key=f"edit_fiber_{edit_food_id}")
                        edit_sodium = st.number_input("Sodium (mg)", min_value=0.0, step=1.0, value=food_to_edit_obj.sodium, key=f"edit_sodium_{edit_food_id}")
                        edit_meal_category = st.selectbox("Meal Category", options=['Breakfast', 'Lunch', 'Dinner', 'Snacks'], 
                                                         index=['Breakfast', 'Lunch', 'Dinner', 'Snacks'].index(getattr(food_to_edit_obj, 'meal_category', 'Snacks')),
                                                         key=f"edit_meal_{edit_food_id}")
                    
                    # Calculate calories from macros
                    edit_calculated_calories = (edit_protein * 4) + (edit_fat * 9) + (edit_carbs * 4)
                    
                    # Use manual calories if provided, otherwise use calculated
                    edit_final_calories = edit_manual_calories if edit_manual_calories > 0 else edit_calculated_calories
                    
                    # Display calorie information
                    if edit_manual_calories > 0:
                        st.info(f"**Using Manual Calories:** {edit_manual_calories:.1f} kcal")
                    else:
                        st.info(f"**Auto-Calculated Calories:** {edit_calculated_calories:.1f} kcal (P: {edit_protein*4:.0f} + F: {edit_fat*9:.0f} + C: {edit_carbs*4:.0f})")
                    
                    # Create two columns for buttons
                    edit_button_col1, edit_button_col2 = st.columns(2)
                    
                    with edit_button_col1:
                        update_button = st.form_submit_button("Update Food", type="primary")
                    with edit_button_col2:
                        cancel_button = st.form_submit_button("Cancel", type="secondary")
                    
                    if cancel_button:
                        st.rerun()
                    
                    if update_button:
                        if edit_food_name:
                            # Update the food log
                            food_to_edit_obj.food_name = edit_food_name
                            food_to_edit_obj.calories = edit_final_calories
                            food_to_edit_obj.protein = edit_protein
                            food_to_edit_obj.fat = edit_fat
                            food_to_edit_obj.carbs = edit_carbs
                            food_to_edit_obj.fiber = edit_fiber
                            food_to_edit_obj.sodium = edit_sodium
                            food_to_edit_obj.meal_category = edit_meal_category
                            
                            session.commit()
                            st.success(f"Updated {edit_food_name}!")
                            st.rerun()
                        else:
                            st.error("Please enter a food name")
    
    # Delete food section
    if food_logs:
        st.divider()
        st.subheader("🗑️ Delete Food")
        food_to_delete = st.selectbox(
            "Select food to delete",
            options=[f"{log.food_name} ({getattr(log, 'meal_category', 'Snacks')}) - ID: {log.id}" for log in food_logs]
        )
        
        if st.button("Delete Selected Food"):
            food_id = int(food_to_delete.split("ID: ")[1])
            session.query(FoodLog).filter_by(id=food_id).delete()
            session.commit()
            st.success("Food deleted!")
            st.rerun()
    
    session.close()

def progress_page():
    st.title(f"📈 Progress Tracking - {st.session_state.logged_in_user}")
    
    # Navigation
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("← Back to Profile"):
            st.session_state.page = 'profile'
            st.rerun()
    with col2:
        if st.button("📝 Food Log"):
            st.session_state.page = 'food_log'
            st.rerun()
    with col3:
        if st.button("Logout"):
            st.session_state.logged_in_user = None
            st.session_state.page = 'login'
            st.rerun()
    
    # Get user data
    session = Session()
    profile = session.query(UserProfile).filter_by(
        username=st.session_state.logged_in_user
    ).first()
    
    if not profile:
        st.warning("Please complete your profile first!")
        session.close()
        return
    
    # Get all weight logs for this user
    weight_logs = session.query(WeightLog).filter_by(
        username=st.session_state.logged_in_user
    ).order_by(WeightLog.log_date).all()
    
    if not weight_logs:
        st.info("📊 No weight data logged yet. Start logging your weight on the Food Log page!")
        session.close()
        return
    
    # Create dataframe for plotting
    weight_data = pd.DataFrame([
        {
            'Date': log.log_date,
            'Weight': log.weight,
            'Notes': log.notes
        }
        for log in weight_logs
    ])
    
    # Calculate statistics
    current_weight = weight_logs[-1].weight
    starting_weight = weight_logs[0].weight
    weight_change = current_weight - starting_weight
    target_weight = profile.target_weight
    remaining_to_goal = target_weight - current_weight
    
    # Display key metrics
    st.subheader("📊 Overview")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Current Weight",
            f"{current_weight:.1f} lbs",
            delta=f"{weight_change:+.1f} lbs since start"
        )
    with col2:
        st.metric(
            "Starting Weight",
            f"{starting_weight:.1f} lbs"
        )
    with col3:
        st.metric(
            "Target Weight",
            f"{target_weight:.1f} lbs"
        )
    with col4:
        st.metric(
            "To Goal",
            f"{abs(remaining_to_goal):.1f} lbs",
            delta=f"{remaining_to_goal:+.1f} lbs"
        )
    
    # Progress bar
    if starting_weight != target_weight:
        total_to_lose = target_weight - starting_weight
        progress_percentage = ((starting_weight - current_weight) / total_to_lose) * 100
        progress_percentage = max(0, min(100, progress_percentage))  # Clamp between 0-100
        st.progress(progress_percentage / 100)
        st.write(f"**Progress: {progress_percentage:.1f}%** of goal reached")
    
    # Weight chart
    st.subheader("📉 Weight Trend")
    
    # Create line chart
    import plotly.graph_objects as go
    
    fig = go.Figure()
    
    # Add weight line
    fig.add_trace(go.Scatter(
        x=weight_data['Date'],
        y=weight_data['Weight'],
        mode='lines+markers',
        name='Actual Weight',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=8)
    ))
    
    # Calculate target weight for each day based on days to target date
    # Create target line data points
    target_dates = []
    target_weights_list = []
    
    # Get the date range
    start_date = weight_data['Date'].min()
    end_date = max(weight_data['Date'].max(), profile.target_date)
    
    # Create daily target weights
    current_date = start_date
    while current_date <= end_date:
        days_until_target = (profile.target_date - current_date).days
        
        # Calculate target weight based on days remaining
        if days_until_target >= 3:
            daily_target = target_weight * 1.05  # 3+ days: +5%
        elif days_until_target == 2:
            daily_target = target_weight * 1.039  # 2 days: +3.9%
        elif days_until_target == 1:
            daily_target = target_weight * 1.021  # 1 day: +2.1%
        else:
            daily_target = target_weight  # Day 0: target weight
        
        target_dates.append(current_date)
        target_weights_list.append(daily_target)
        current_date += pd.Timedelta(days=1)
    
    # Add target progression line
    fig.add_trace(go.Scatter(
        x=target_dates,
        y=target_weights_list,
        mode='lines+markers',
        name='Target Progression',
        line=dict(color='#2ca02c', width=2, dash='dash'),
        marker=dict(size=6)
    ))
    
    # Update layout
    fig.update_layout(
        title='Weight Over Time vs Target Progression',
        xaxis_title='Date',
        yaxis_title='Weight (lbs)',
        hovermode='x unified',
        height=500,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Explanation of target line
    st.info("""
    **How to Read the Chart:**
    - 🔵 **Blue line with markers**: Your actual daily weight
    - 🟢 **Green dashed line**: Target weight progression showing where you should be each day
    
    The target line automatically adjusts based on how many days remain until your weigh-in:
    - **3+ days out**: Target weight +5%
    - **2 days out**: Target weight +3.9%
    - **1 day out**: Target weight +2.1%
    - **Weigh-in day**: Target weight (goal!)
    
    Your actual weight should stay at or below the green line to stay on track.
    """)
    
    # Statistics
    st.subheader("📈 Statistics")
    
    if len(weight_logs) > 1:
        # Calculate rate of change
        days_tracked = (weight_logs[-1].log_date - weight_logs[0].log_date).days
        if days_tracked > 0:
            avg_change_per_day = weight_change / days_tracked
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    "Average Change per Day",
                    f"{avg_change_per_day:+.2f} lbs/day"
                )
            
            # Predict days to goal
            if remaining_to_goal != 0 and avg_change_per_day != 0:
                if (remaining_to_goal > 0 and avg_change_per_day > 0) or (remaining_to_goal < 0 and avg_change_per_day < 0):
                    days_to_goal = abs(remaining_to_goal / avg_change_per_day)
                    st.info(f"📅 At current rate, you'll reach your goal in approximately **{int(days_to_goal-1)} days**")
    
    # Weight log table
    st.subheader("📝 Weight History")
    
    # Reverse the dataframe to show most recent first
    display_data = weight_data.sort_values('Date', ascending=False).copy()
    
    # Convert Date to datetime if it's not already, then format as string
    if not pd.api.types.is_datetime64_any_dtype(display_data['Date']):
        display_data['Date'] = pd.to_datetime(display_data['Date'])
    display_data['Date'] = display_data['Date'].dt.strftime('%Y-%m-%d')
    
    display_data['Weight'] = display_data['Weight'].apply(lambda x: f"{x:.1f} lbs")
    
    st.dataframe(display_data, hide_index=True, use_container_width=True)
    
    # Delete weight entry
    if weight_logs:
        st.subheader("🗑️ Delete Weight Entry")
        dates_to_delete = [f"{log.log_date} - {log.weight} lbs" for log in weight_logs]
        date_to_delete = st.selectbox("Select date to delete", dates_to_delete)
        
        if st.button("Delete Selected Entry", type="secondary"):
            # Extract date from selection
            delete_date_str = date_to_delete.split(" - ")[0]
            delete_date = datetime.strptime(delete_date_str, '%Y-%m-%d').date()
            
            session.query(WeightLog).filter_by(
                username=st.session_state.logged_in_user,
                log_date=delete_date
            ).delete()
            session.commit()
            st.success("Weight entry deleted!")
            st.rerun()
    
    session.close()

# Main app logic
if st.session_state.page == 'login':
    login_page()
elif st.session_state.page == 'profile':
    profile_page()
elif st.session_state.page == 'food_log':
    food_log_page()
elif st.session_state.page == 'progress':
    progress_page()
