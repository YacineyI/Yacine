# Overview

This is a Highrise Bot project built in Python that provides advanced bot functionality for the Highrise virtual world platform. The bot includes features for outfit management, user moderation, movement controls, and a web-based file management interface. It's designed to manage virtual spaces with comprehensive user interaction capabilities, automated behaviors, and administrative tools.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Bot Framework
- **Core Platform**: Built on the Highrise Bot SDK (version 23.3.4)
- **Async Architecture**: Uses asyncio for handling concurrent bot operations and real-time interactions
- **Configuration Management**: Centralized config system with environment variable support for sensitive data

## Web Interface
- **Framework**: Flask web server for file management and bot configuration
- **Template Engine**: Jinja2 templates with Arabic RTL support
- **Real-time Updates**: File watching system using watchdog for live code updates

## Bot Features Architecture
- **Outfit Management System**: Dedicated OutfitManager class handling clothing codes validation and outfit changes
- **User Management**: Role-based access control with owner, admin, VIP, and banned user categories
- **Movement System**: Automated random movement with configurable intervals and spawn positions
- **Moderation Tools**: Built-in spam protection, word filtering, and user management capabilities

## Data Storage
- **Configuration**: Python-based config with JSON data persistence for moderators
- **File Management**: Direct file system operations with secure filename handling
- **State Management**: In-memory state management for active bot sessions

## Security & Privacy
- **Credential Management**: Environment variable support for sensitive bot tokens and room IDs
- **Access Control**: Multi-tier permission system for different user roles
- **Input Validation**: Comprehensive validation for clothing codes and user inputs

# External Dependencies

## Highrise Platform
- **Highrise Bot SDK**: Primary integration for virtual world interactions
- **Room Management**: Connects to specific Highrise rooms using room IDs
- **User Authentication**: Bot token-based authentication with the Highrise platform

## Web Framework
- **Flask**: Lightweight web server for management interface
- **Werkzeug**: WSGI utilities for secure file handling
- **Jinja2**: Template rendering for web interface

## Utility Libraries
- **aiohttp**: Asynchronous HTTP client for external API calls
- **watchdog**: File system monitoring for live code updates
- **pendulum**: Enhanced date/time handling
- **cattrs**: Data structure serialization

## Development Tools
- **typing-extensions**: Enhanced type hints for better code documentation
- **six**: Python 2/3 compatibility utilities

The bot requires environment variables for `ROOM_ID` and `BOT_TOKEN` to connect to the Highrise platform, and supports deployment on platforms like Replit with built-in secrets management.