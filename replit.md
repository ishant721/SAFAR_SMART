# Overview

SafarSmart is a comprehensive Django-based travel itinerary planning web application that leverages AI-powered agents to create personalized travel experiences. The platform allows users to create detailed trip plans with intelligent suggestions for accommodations, activities, weather forecasts, packing lists, and expense breakdowns. The application integrates multiple AI agents using LangGraph workflows to provide a complete travel planning solution with payment functionality for premium features.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Architecture

The application follows Django's Model-View-Template (MVT) pattern with a modular app structure:

- **Django Framework**: Core web framework handling routing, authentication, and request processing
- **Modular App Design**: Separated into distinct Django apps (`users`, `planner`, `payments`) for clear separation of concerns
- **Custom User Model**: Extended Django's AbstractUser to include OTP functionality and payment tracking fields
- **RESTful API**: Django REST Framework provides API endpoints with JWT authentication for frontend communication

## AI Agent System

The core innovation lies in the LangGraph-powered AI agent network:

- **LangGraph Workflow**: Sequential execution of specialized AI agents for comprehensive trip planning
- **Google Generative AI Integration**: Uses Gemini 2.5 Pro model for intelligent content generation
- **Specialized Agent Architecture**:
  - Itinerary Generator: Creates day-by-day travel plans
  - Accommodation Recommender: Suggests lodging options with ratings and booking links
  - Expense Breakdown Agent: Calculates and categorizes trip costs
  - Activity Recommender: Suggests local attractions and experiences
  - Weather Forecaster: Provides destination-specific weather insights
  - Packing List Generator: Creates tailored packing recommendations
  - Food & Culture Agent: Recommends local cuisine and cultural etiquette
  - Chat Agent: Handles user interactions and plan modifications

## Data Storage

- **SQLite Database**: Development database with Django ORM for data modeling
- **JSON Fields**: Used for storing complex nested data from AI agents (activity suggestions, weather data, etc.)
- **Migration System**: Django's built-in migration system for schema management
- **Model Relationships**: Foreign key relationships linking users to trips and chat messages

## Authentication & Authorization

- **JWT Token Authentication**: Secure API access using djangorestframework-simplejwt
- **OTP Verification**: Email-based verification for user registration and password reset
- **Session-based Authentication**: Standard Django session management for web interface
- **Custom User Fields**: Tracks free and prepaid itinerary counts for usage limits

## Payment System Integration

- **Razorpay Integration**: Payment gateway for processing transactions
- **Wallet System**: User credit system for purchasing itineraries
- **Payment Tracking**: Complete payment history and transaction management
- **Freemium Model**: Limited free itineraries with paid options for additional features

## Frontend Architecture

- **Server-side Rendering**: Django templates with Bootstrap for responsive design
- **Modern CSS Framework**: Custom CSS with CSS variables for theming and responsive design
- **Progressive Enhancement**: JavaScript functionality layered over server-rendered HTML
- **Component-based Templates**: Modular template structure with template inheritance

## Search and External APIs

- **Google Serper API**: Web search capabilities for gathering travel information
- **Markdown Processing**: Converts AI-generated markdown content to HTML for display
- **Template Filters**: Custom Django template filters for enhanced data presentation

# External Dependencies

## AI and Machine Learning
- **LangChain**: Framework for building AI agent applications
- **LangGraph**: Workflow orchestration for multi-agent AI systems
- **Google Generative AI**: Gemini 2.5 Pro model for content generation
- **LangChain Community**: Additional tools and utilities for AI applications

## Payment Processing
- **Razorpay**: Payment gateway for processing transactions and managing orders
- **Webhook Integration**: Real-time payment status updates

## Web Framework and API
- **Django**: Core web framework and ORM
- **Django REST Framework**: API development and serialization
- **Django REST Framework SimpleJWT**: JWT token authentication

## Search and Data
- **Google Serper API**: Web search functionality for travel information gathering
- **Markdown**: Content formatting and HTML conversion

## Development Tools
- **Python Dotenv**: Environment variable management
- **Django Extensions**: Additional development utilities

## Frontend Dependencies
- **Bootstrap 5.3.2**: CSS framework for responsive design
- **Bootstrap Icons**: Icon library for UI elements
- **Inter Font**: Typography from Google Fonts
- **Custom CSS Variables**: Theme management and consistent styling

The application is designed to be easily deployable on cloud platforms with environment-based configuration management and follows Django best practices for scalability and maintainability.