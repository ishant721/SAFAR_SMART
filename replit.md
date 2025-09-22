# Overview

SafarSmart is a comprehensive AI-powered travel itinerary planning web application built with Django. The platform allows users to create personalized travel plans through an intelligent multi-agent system powered by LangChain and LangGraph. Users can generate detailed itineraries, get accommodation recommendations, expense breakdowns, activity suggestions, weather forecasts, and packing lists. The application includes a freemium model with payment integration via Razorpay, allowing users to purchase additional itinerary generations after exhausting their free quota.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Framework
- **Django**: Main web framework providing MVC architecture
- **Django REST Framework**: API endpoints for frontend interactions
- **Django Simple JWT**: Token-based authentication system

## AI-Powered Planning Engine
- **LangChain/LangGraph**: Multi-agent workflow system for intelligent trip planning
- **Google Generative AI (Gemini 2.0 Flash)**: Primary language model for content generation
- **Specialized AI Agents**: 
  - Itinerary Generator for day-by-day planning
  - Accommodation Recommender for lodging suggestions
  - Expense Breakdown Agent for cost estimation
  - Activity Recommender for local attractions
  - Weather Forecaster for climate information
  - Packing List Generator for travel preparation
  - Food & Culture Recommender for dining and cultural insights
  - Complete Trip Plan Synthesizer for final consolidation
  - Interactive Chat Agent for user modifications

## Database Architecture
- **SQLite**: Development database (Django default)
- **Models**:
  - User: Extended Django user with OTP verification and payment tracking
  - Trip: Core trip entity with comprehensive planning data
  - ChatMessage: AI assistant conversation history
  - Checkpoint: Interactive journey progress tracking
  - Payment: Transaction records for Razorpay integration
  - UserProfile: Additional user metadata and credits

## Authentication System
- **Email-based registration**: Users register with email instead of username
- **OTP verification**: Two-factor authentication for registration and password reset
- **JWT tokens**: Secure API authentication
- **Session-based authentication**: Web interface authentication

## Payment Integration
- **Freemium model**: 2 free itineraries per user
- **Razorpay integration**: Payment processing for additional itineraries
- **Wallet system**: Users can add money and purchase itinerary credits
- **Prepaid credits**: Support for bulk itinerary purchases

## Frontend Architecture
- **Server-side rendering**: Django templates with Bootstrap 5
- **Responsive design**: Mobile-first approach with modern CSS
- **Interactive elements**: JavaScript for dynamic content and AJAX requests
- **Progressive enhancement**: Core functionality works without JavaScript

# External Dependencies

## AI and Machine Learning
- **Google Generative AI API**: Primary LLM for content generation (Gemini 2.0 Flash)
- **Serper API**: Web search capabilities for real-time information retrieval
- **LangChain Community**: Extended tools and utilities for AI workflows

## Payment Processing
- **Razorpay**: Payment gateway for handling transactions, wallet top-ups, and subscription management
- **Razorpay Webhooks**: Real-time payment status updates

## Communication Services
- **Django Email Backend**: SMTP email service for OTP delivery, notifications, and trip confirmations
- **Email Templates**: HTML email templates for user communications

## Development and Deployment
- **Python-dotenv**: Environment variable management
- **Gunicorn**: WSGI HTTP server for production deployment
- **Bootstrap 5**: Frontend CSS framework with modern components
- **Bootstrap Icons**: Icon library for UI elements

## Document Generation
- **FPDF2**: PDF generation for downloadable trip plans and itineraries
- **Markdown**: Content formatting and HTML conversion utilities

## External APIs
- **Weather APIs**: Real-time weather data integration
- **Search APIs**: Activity and accommodation recommendation data
- **Maps and Location Services**: Geographic data for trip planning