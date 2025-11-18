# 🏋️ Weight Tracker App

A comprehensive Streamlit-based weight tracking application designed for athletes, fitness enthusiasts, and anyone working towards weight goals. Features intelligent macro tracking, food logging with a 74,000+ food database, and progress visualization with target progression tracking.

## 🌟 Features

### 📊 **Smart Weight Tracking**
- Daily weight logging with notes
- Interactive progress charts comparing actual weight vs target progression
- Automatic target weight calculations based on days remaining
- Built-in weight cutting guidelines (3+ days: +5%, 2 days: +3.9%, 1 day: +2.1%)
- Progress statistics and goal predictions

### 🍽️ **Comprehensive Food Logging**
- Search from 74,000+ foods in USDA nutritional database
- Manual food entry with automatic calorie calculation
- Add foods by calories OR macros (protein, fat, carbs)
- Edit existing food entries
- Organize meals by category (Breakfast, Lunch, Dinner, Snacks)
- Copy entire meals from previous days
- Track fiber and sodium for weight cutting

### 📈 **Dynamic Macro & Micro Tracking**
- Automatic macro calculation based on:
  - Current weight
  - Target weight
  - Days to goal
  - Activity level (sedentary to very active)
- Real-time macro breakdown (protein, fat, carbs)
- Micronutrient tracking (fiber, sodium) with day-specific targets
- Progress bars showing daily intake vs targets

### 👤 **User Profiles**
- Secure user authentication
- Personalized profiles with:
  - Current weight & target weight
  - Target date
  - Height
  - Body fat percentage (optional)
- Multiple users supported

## 🚀 Getting Started

### Try It Online
Visit the live app: [Your App URL Here]

### Or Run Locally

#### Prerequisites
- Python 3.8 or higher
- pip (Python package installer)

#### Installation

1. **Clone or download this repository**
   ```bash
   git clone [your-repo-url]
   cd weight-tracker-app
   ```

2. **Install required packages**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   streamlit run app.py
   ```

4. **Access the app**
   - The app will automatically open in your default browser
   - If not, navigate to `http://localhost:8501`

## 📖 How to Use

### First Time Setup

1. **Create an Account**
   - Click "Sign Up" on the login page
   - Choose a unique username and password
   - Note: Passwords are stored securely

2. **Set Up Your Profile**
   - Enter your current weight
   - Set your target weight
   - Choose your target date
   - Add height and optional body fat percentage
   - Click "Save Profile"

### Daily Use

#### **1. Log Your Weight**
- Go to "Food Log" page
- Click "Log Weight for Today"
- Enter your current weight
- Add optional notes
- View your weight automatically appears on charts

#### **2. Track Your Food**

**Option A: Search Food Database**
- Search for any food (e.g., "chicken breast")
- Enter portion size in grams
- Select meal category
- Click "Add Food"

**Option B: Manual Entry**
- Enter food name
- Add calories directly OR enter macros (protein, fat, carbs)
- If you enter macros, calories calculate automatically
- Add fiber and sodium if tracking
- Click "Add Manually"

**Option C: Copy Past Meals**
- Click "Copy Past Meals"
- Select a previous date
- Choose which meal categories to copy
- Click "Copy Selected Meals"

#### **3. Edit Food Entries**
- Scroll to "Edit Food" section
- Select the food you want to edit
- Modify any values (name, macros, meal category)
- Click "Update Food"

#### **4. View Progress**
- Navigate to "Progress Tracking" page
- See your weight trend chart with target progression
- View statistics and goal predictions
- Check your complete weight history

## 📊 Understanding Your Targets

### Weight Target Progression
The app uses a strategic weight cutting progression:
- **3+ days out**: Stay at or below target weight + 5%
- **2 days out**: Stay at or below target weight + 3.9%
- **1 day out**: Stay at or below target weight + 2.1%
- **Weigh-in day**: Hit your target weight

### Macro Targets
Automatically calculated based on:
- **Protein**: 1g per pound of body weight
- **Fat**: 25% of total calories (adjustable in profile)
- **Carbs**: Remaining calories

### Activity Level Multipliers
- **Sedentary**: 1.2x (little to no exercise)
- **Lightly Active**: 1.375x (exercise 1-3 days/week)
- **Moderately Active**: 1.55x (exercise 3-5 days/week)
- **Very Active**: 1.725x (exercise 6-7 days/week)
- **Extremely Active**: 1.9x (physical job + exercise)

### Micro Targets (Weight Cutting Days)
- **3 days out**: 8g fiber, 1500mg sodium
- **2 days out**: 5g fiber, 1000mg sodium
- **1 day out**: 4g fiber, 800mg sodium
- **Other days**: 30g fiber, 2300mg sodium

## 🎯 Use Cases

### For Athletes
- Track weight for competitions (wrestling, boxing, MMA, etc.)
- Monitor weight cutting progression
- Ensure adequate nutrition while making weight

### For Fitness Enthusiasts
- Track daily weight trends
- Monitor macro intake for body composition goals
- Log and analyze food choices

### For General Health
- Track weight loss or gain progress
- Learn about nutritional content of foods
- Build healthy eating habits with data

## 📁 File Structure

```
weight-tracker-app/
├── app.py                  # Main application file
├── requirements.txt        # Python dependencies
├── food_nutrition.db       # USDA food database (74,000+ foods)
├── weight_tracker.db       # User data (created automatically)
└── README.md              # This file
```

## 🗄️ Database Files

- **food_nutrition.db**: Contains nutritional information for 74,000+ foods from USDA database (required, included in repo)
- **weight_tracker.db**: Stores user data, profiles, food logs, and weight logs (created automatically on first run)

## 🔒 Privacy & Data

- All data is stored locally in SQLite databases
- No data is sent to external servers (when running locally)
- Each user's data is isolated and private
- When deployed online, each deployment has its own database

## 🛠️ Technical Details

### Built With
- **Streamlit** - Web application framework
- **SQLAlchemy** - Database ORM
- **Pandas** - Data manipulation
- **Plotly** - Interactive charts
- **SQLite** - Database storage

### Python Version
- Requires Python 3.8 or higher
- Tested on Python 3.9, 3.10, 3.11, 3.12

### Dependencies
All dependencies are listed in `requirements.txt`:
- streamlit
- pandas
- sqlalchemy
- plotly

## ⚠️ Important Notes

### Food Database
- The app requires `food_nutrition.db` to function
- This file contains USDA nutritional data
- Without it, food search will not work

### User Data
- User passwords are stored (consider adding hashing for production use)
- Food logs and weight logs are stored per user
- Data persists between sessions

### Weight Cutting Disclaimer
- The weight cutting features are designed for athletes with experience
- Always consult with a coach or healthcare professional
- Stay hydrated and monitor your health

## 🐛 Troubleshooting

**App won't start:**
- Ensure all packages are installed: `pip install -r requirements.txt`
- Verify Python version: `python --version` (need 3.8+)

**Database errors:**
- Ensure `food_nutrition.db` exists in the same directory as `app.py`
- `weight_tracker.db` will be created automatically

**Port already in use:**
- Specify a different port: `streamlit run app.py --server.port 8502`

**Food search returns no results:**
- Verify `food_nutrition.db` is present and not corrupted
- Try broader search terms (e.g., "chicken" instead of "grilled chicken breast")

## 🚀 Deployment

This app can be deployed to Streamlit Community Cloud for free:

1. Upload files to a public GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click "Create app"
4. Select your repository and `app.py`
5. Deploy!

For detailed deployment instructions, see the [Streamlit Deployment Documentation](https://docs.streamlit.io/deploy).

## 📝 Future Enhancements

Potential features for future versions:
- [ ] Password hashing for improved security
- [ ] Export data to CSV/Excel
- [ ] Custom meal templates
- [ ] Barcode scanning for food entry
- [ ] Integration with fitness trackers
- [ ] Multiple weight goal tracking
- [ ] Nutrition reports and insights
- [ ] Recipe calculator
- [ ] Progress photos

## 🤝 Contributing

This is a personal project, but suggestions and feedback are welcome! If you find bugs or have ideas for improvements, please open an issue.

## 📄 License

This project is open source and available for personal use.

## 🙏 Acknowledgments

- USDA FoodData Central for the comprehensive nutritional database
- Streamlit team for the amazing web framework
- The fitness and nutrition community for inspiration

## 📧 Contact

For questions or feedback about this app, please [open an issue](your-repo-url/issues) on GitHub.

---

**Made with 💪 for athletes and fitness enthusiasts**

*Track smart. Perform better.*
