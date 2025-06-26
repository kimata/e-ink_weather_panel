# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

E-Ink Weather Panel is a Python application that generates comprehensive weather display images for e-ink displays connected to Raspberry Pi devices. The system integrates data from Yahoo Weather API, Japan Meteorological Agency rain radar, and InfluxDB sensor data to create multi-panel weather displays.

## Development Commands

### Python Environment (Rye)

```bash
# Install dependencies
rye sync

# Run main application locally
env RASP_HOSTNAME="hostname" rye run python src/display_image.py

# Run basic functionality tests
rye run pytest --timeout=240 --numprocesses=auto --verbosity=1 tests/test_basic.py

# Run all tests with coverage
rye run pytest --cov=src --cov-report=html tests/

# Run web interface tests (requires host IP)
rye run pytest tests/test_playwright.py --host <host-ip>
```

### React Frontend

```bash
cd react

# Install dependencies
npm ci

# Development server
npm run dev

# Build for production
npm run build

# Lint code
npm run lint
```

### Docker Development

```bash
# Build frontend first
cd react && npm ci && npm run build && cd -

# Run with Docker Compose
docker compose run --build --rm weather_panel
```

## Architecture

### Core Components

- **Image Generation**: `src/create_image.py` - Main entry point for generating weather panel images
- **Display Control**: `src/display_image.py` - Handles e-ink display on Raspberry Pi
- **Web Interface**: `src/webapp.py` - Flask web API for remote image generation

### Weather Display Modules (`src/weather_display/`)

- `weather_panel.py` - Weather forecast with Yahoo Weather API integration
- `rain_cloud_panel.py` - Rain radar from Japan Meteorological Agency
- `sensor_graph.py` - InfluxDB sensor data visualization (temperature, humidity, etc.)
- `power_graph.py` - Power consumption monitoring graphs
- `wbgt_panel.py` - WBGT heat index calculation and display
- `time_panel.py` - Current time display
- `generator.py` - Web-based image generation interface

### Configuration

- Two display modes: Normal (3200x1800) and Small (2200x1650)
- YAML configuration with JSON schema validation
- Environment-specific configs: `config.yaml` and `config-small.yaml`

### Data Sources

- **Weather**: Yahoo Weather API for forecasts
- **Rain Radar**: Japan Meteorological Agency real-time images
- **Sensors**: InfluxDB for local environmental data
- **Power**: Energy consumption monitoring

## Testing Strategy

Tests are organized by component with specific focus areas:

- `test_basic.py` - Core functionality walkthrough
- `test_playwright.py` - Web interface testing
- Component-specific tests for each weather panel type

Coverage reports are generated in `tests/evidence/coverage/`.

## Deployment

- **Local**: Direct Python execution with Rye
- **Docker**: Multi-stage builds with frontend compilation
- **Kubernetes**: Production deployment with persistent volumes
- **CI/CD**: GitLab CI with comprehensive test matrix

## Key Dependencies

- **Backend**: PIL/Pillow for image processing, requests for API calls, InfluxDB client
- **Frontend**: React + TypeScript with Vite build system
- **Display**: Raspberry Pi e-ink display drivers
- **Fonts**: Custom Japanese fonts (migmix) for internationalization

The system is designed for reliability in IoT environments with comprehensive error handling, caching, and fallback mechanisms.
