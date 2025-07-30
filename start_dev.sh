#!/bin/bash

# --- Configuration ---
BACKEND_DIR="whatmovie_backend"
FRONTEND_DIR="whatmovie-frontend"
VENV_NAME="venv"




# --- Helper Functions ---

# Function to check if a command exists
command_exists () {
  type "$1" &> /dev/null ;
}

# Function to handle errors and exit
handle_error() {
  echo "Error: $1"
  exit 1
}

# Function to clean up background processes on script exit
cleanup() {
  echo -e "\nShutting down development servers..."
  # Kill the backend server
  if [ -n "$BACKEND_PID" ]; then
    kill "$BACKEND_PID" 2>/dev/null
    echo "Django backend stopped."
  fi
  # Kill the frontend server
  if [ -n "$FRONTEND_PID" ]; then
    kill "$FRONTEND_PID" 2>/dev/null
    echo "React frontend stopped."
  fi
  exit 0
}

# Trap Ctrl+C (SIGINT) and SIGTERM to call the cleanup function
trap cleanup SIGINT SIGTERM




# --- Main Script Logic ---

echo "--- Setting up and launching WhatMovie development environment ---"



# --- 1. Backend Setup (Django) ---
echo -e "\n--- Setting up Django Backend ---"
if [ ! -d "$BACKEND_DIR" ]; then
  handle_error "Backend directory '$BACKEND_DIR' not found. Please check your path."
fi
cd "$BACKEND_DIR" || handle_error "Failed to change to backend directory."

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_NAME" ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv "$VENV_NAME" || handle_error "Failed to create virtual environment."
fi

# Activate virtual environment
echo "Activating virtual environment..."
# Check if running on Windows (Git Bash/WSL) or Linux/macOS
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
  source "$VENV_NAME/Scripts/activate" || handle_error "Failed to activate venv (Windows)."
else
  source "$VENV_NAME/bin/activate" || handle_error "Failed to activate venv (Linux/macOS)."
fi

# Install Python dependencies
if [ -f "requirements.txt" ]; then
  echo "Installing Python dependencies from requirements.txt..."
  pip install -r requirements.txt || handle_error "Failed to install Python dependencies."
else
  echo "Warning: requirements.txt not found in $BACKEND_DIR. Skipping pip install."
  echo "Please ensure all Python dependencies are manually installed."
fi

# Run Django migrations
echo "Running Django migrations..."
python manage.py makemigrations || handle_error "Failed to run makemigrations."
python manage.py migrate || handle_error "Failed to run migrate."

echo "Deactivating virtual environment..."
deactivate

# Return to parent directory
cd .. || handle_error "Failed to return to parent directory."



# --- 2. Frontend Setup (React) ---
echo -e "\n--- Setting up React Frontend ---"
if [ ! -d "$FRONTEND_DIR" ]; then
  handle_error "Frontend directory '$FRONTEND_DIR' not found. Please check your path."
fi
cd "$FRONTEND_DIR" || handle_error "Failed to change to frontend directory."

# Install Node.js dependencies
echo "Installing Node.js dependencies..."
npm install || handle_error "Failed to install Node.js dependencies."

# Initialize Tailwind CSS (if not already done)
# This will create tailwind.config.js if it doesn't exist
if [ ! -f "tailwind.config.js" ]; then
  echo "Initializing Tailwind CSS configuration..."
  npx tailwindcss init || handle_error "Failed to initialize Tailwind CSS."
else
  echo "tailwind.config.js already exists. Skipping Tailwind CSS initialization."
fi

# Return to parent directory
cd .. || handle_error "Failed to return to parent directory."



# --- 3. Launch Servers ---
echo -e "\n--- Launching Development Servers ---"

# Launch Django Backend in background
echo "Starting Django backend (http://127.0.0.1:8000/)..."
cd "$BACKEND_DIR" || handle_error "Failed to change to backend directory."
# Activate venv again for the server process
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
  source "$VENV_NAME/Scripts/activate"
else
  source "$VENV_NAME/bin/activate"
fi
python manage.py runserver & # Run in background
BACKEND_PID=$!
cd .. # Return to parent directory

# Launch React Frontend in background
echo "Starting React frontend (http://localhost:3000/)..."
cd "$FRONTEND_DIR" || handle_error "Failed to change to frontend directory."
npm start & # Run in background
FRONTEND_PID=$!
cd .. # Return to parent directory

echo -e "\nBoth servers are running. Press Ctrl+C to stop both."

# Wait for any background process to exit (e.g., if one crashes or is manually stopped)
# This keeps the script alive until cleanup is triggered.
wait -n "$BACKEND_PID" "$FRONTEND_PID"

# If one process exits, cleanup will be called by the trap.
# This line is reached if wait returns due to a child process exiting.
cleanup
