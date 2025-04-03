# Abode - Interior Design AI Assistant

Abode is an AI-powered interior design assistant that helps you transform your living spaces with personalized furniture recommendations and style suggestions.

## Features

- **Room Decorator**: Upload room images and receive AI-generated furniture and decor recommendations
- **Style Recommender**: Discover your personal interior design style through an interactive preference quiz
- **Style Image Collection**: Browse curated images of different interior design styles for inspiration
- **Web Interface**: Streamlit-based UI that allows you to swipe on style examples and get personalized recommendations

## Setup

1. Clone this repository
2. Install dependencies using Poetry:
   ```
   poetry install
   ```
3. Create a `.env` file in the project root with API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   PEXELS_API_KEY=your_pexels_api_key_here
   ```

   > **Important:** Both API keys are required for the application to function:
   > - Get an OpenAI API key from https://platform.openai.com/api-keys
   > - Get a free Pexels API key from https://www.pexels.com/api/

## Components

### Room Decorator

Upload images of your room and get AI-generated recommendations for furniture and decor based on the current space.

```
poetry run python room_decorator.py
```

### Style Recommender

Discover your interior design style preferences through an interactive quiz that shows you various style images.

```
poetry run python style_recommender.py
```

### Style Image Downloader

Download and organize interior design style images for the style recommender. This script uses the Pexels API to gather high-quality images.

```
poetry run python style_image_downloader.py
```

### Streamlit Web App (New!)

Our new web interface combines style selection and room decoration in a user-friendly interface with a swipe-based UI.

```
poetry run streamlit run streamlit_app.py
```

Features of the Streamlit app:
- Swipe through 5 random style examples to indicate your preferences
- Upload a photo of your empty room
- Get personalized design recommendations based on your style preferences and room layout
- View the results in a tabbed interface organized by style analysis, room analysis, and specific recommendations

## Workflow

1. First run `style_image_downloader.py` to gather style images
2. Launch the Streamlit app with `streamlit run streamlit_app.py`
3. Swipe through style examples (like or dislike)
4. Upload your empty room photo
5. Get personalized recommendations based on your preferences

## Requirements

- Python 3.8+
- Poetry for dependency management
- OpenAI API key with access to GPT-4o
- Pexels API key for image sourcing

## Notes

- The application requires valid API keys to function
- If API keys are missing or invalid, the application will display an error message with instructions
- No fallback functionality is provided - the application depends on real-time AI analysis 