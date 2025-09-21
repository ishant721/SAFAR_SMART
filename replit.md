# Overview

SafarSmart is a comprehensive AI-powered travel itinerary planning web application built with Django. The platform allows users to create personalized travel plans with intelligent recommendations for accommodations, activities, weather forecasts, packing lists, and cultural insights. The application leverages LangChain and LangGraph for AI-driven trip planning, integrated with Google's Gemini AI model and external APIs for real-time data.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Architecture
The application follows Django's MVC pattern with a modular app structure:

- **Core Framework**: Django 5.2+ with Django REST Framework for API endpoints
- **Database**: Default Django ORM (supports SQLite for development, easily extensible to PostgreSQL)
- **Authentication**: Custom user model extending AbstractUser with JWT token support via djangorestframework-simplejwt
- **OTP System**: Built-in email-based verification for registration and password reset

## AI Agent System
The core intelligence is powered by a LangGraph workflow with specialized AI agents:

- **Modular Agent Architecture**: Each planning aspect (itinerary, accommodation, expenses, activities) handled by dedicated agents
- **Sequential Workflow**: LangGraph orchestrates agent execution in logical sequence
- **Chat Interface**: Interactive AI assistant for trip modifications and general queries
- **State Management**: Comprehensive trip state tracking through the workflow

## Payment System
Integrated payment processing using Razorpay:

- **Wallet System**: Users can add funds to their accounts
- **Freemium Model**: Limited free itineraries with paid upgrades
- **Credit System**: Prepaid credits and pay-per-use options

## Data Models
- **User Management**: Custom user model with payment tracking fields
- **Trip Planning**: Comprehensive trip model storing all AI-generated content as JSON fields
- **Interactive Features**: Checkpoint system for trip progress tracking and user feedback

## Frontend Architecture
- **Template-based UI**: Django templates with Bootstrap 5 for responsive design
- **Modern Design System**: Custom CSS with CSS variables for theming
- **Progressive Enhancement**: JavaScript for dynamic interactions and AJAX calls

## File Processing
- **PDF Generation**: fpdf2 for downloadable trip itineraries
- **Email Integration**: HTML email templates for OTP and trip notifications

# External Dependencies

## AI and Language Models
- **Google Gemini AI**: Primary language model via langchain-google-genai
- **LangChain**: Framework for building AI agent workflows
- **LangGraph**: Orchestration of complex AI agent interactions
- **Serper API**: Web search capabilities for real-time travel information

## Payment Processing
- **Razorpay**: Complete payment gateway integration for wallet top-ups and itinerary purchases

## Communication Services
- **SMTP Email**: Email delivery for OTP verification and trip notifications
- **Django Email Backend**: Configurable email system with HTML template support

## Development and Deployment
- **Gunicorn**: WSGI server for production deployment
- **Static File Handling**: Django's built-in static file management
- **Environment Configuration**: python-dotenv for secure credential management

## API Integration
- **Weather Services**: Integrated weather forecasting for destination planning
- **Search APIs**: Real-time accommodation and activity recommendations
- **External Content**: Dynamic fetching of travel guides and cultural information

The architecture prioritizes modularity, scalability, and user experience while maintaining secure payment processing and reliable AI-powered trip planning capabilities.