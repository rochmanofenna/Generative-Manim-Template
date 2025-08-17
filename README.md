# Generative Manim Template

<p align="center">
  <h1 align="center">Educational Video Generation Platform</h1>
</p>

<p align="center">
  AI-powered educational video generation using Manim animations
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" />
  <img src="https://img.shields.io/badge/Manim-0.18.0+-orange.svg" />
  <img src="https://img.shields.io/badge/Flask-2.3.0+-green.svg" />
  <img src="https://img.shields.io/badge/OpenAI-GPT4o-purple.svg" />
  <img src="https://img.shields.io/badge/Anthropic-Claude-red.svg" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" />
</p>

---

## Features

- **AI-Powered Generation**: Create professional educational videos using GPT-4o, Claude, and other LLMs
- **Mathematical Animations**: Advanced Manim integration for complex formulas, graphs, and visualizations
- **Text-to-Speech**: Automated voiceover generation with Google TTS
- **Multiple Formats**: Support for 16:9, 9:16, and 1:1 aspect ratios
- **Real-time Streaming**: Live progress updates during video generation
- **Interactive Chat**: Iterative refinement with preview generation
- **Domain Flexibility**: Configurable for any educational domain (math, science, programming, etc.)
- **Docker Ready**: Containerized deployment for consistent environments

## Quick Start

### Prerequisites

- Python 3.9+
- FFmpeg
- LaTeX (for mathematical formulas)
- Docker (optional)

### 1. Clone Repository

```bash
git clone https://github.com/rochmanofenna/Generative-Manim-Template.git
cd Generative-Manim-Template
```

### 2. Environment Setup

```bash
# Install using pip
pip install -e .

# Or install with development dependencies
make install-dev

# Or manually install
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory:

```bash
# Required API Keys
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Storage Configuration (choose one)
USE_LOCAL_STORAGE=true
BASE_URL=http://localhost:5001

# Optional: Cloud Storage
AZURE_STORAGE_CONNECTION_STRING=your_azure_connection
AZURE_STORAGE_CONTAINER_NAME=your_container
GOOGLE_CLOUD_FILE=path/to/service-account.json
GOOGLE_BUCKET_NAME=your_bucket_name

# Optional: Domain Configuration
DOMAIN_CONFIG=config/domains/mathematics.json
```

### 4. Run the Application

```bash
# Using make
make run

# Or directly
python api/run.py

# Or with gunicorn (production)
make run-prod
```

The API will be available at `http://localhost:5001`

## Usage

### Simple Video Generation

```bash
curl -X POST http://localhost:5001/v1/video/rendering \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain the quadratic formula with visual examples",
    "model": "gpt-4o",
    "user_id": "demo",
    "project_name": "math-tutorial",
    "iteration": "v1",
    "aspect_ratio": "16:9",
    "disable_voiceover": false
  }'
```

### Interactive Chat Generation

```bash
curl -X POST http://localhost:5001/v1/chat/generation \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Create a video about Newton's laws of motion"}
    ],
    "engine": "openai",
    "model": "gpt-4o"
  }'
```

### Domain-Specific Examples

The platform supports multiple educational domains. Configure your domain in `config/domains/`:

- **Mathematics**: Calculus, linear algebra, statistics
- **Physics**: Mechanics, thermodynamics, quantum physics  
- **Computer Science**: Algorithms, data structures, machine learning
- **Chemistry**: Organic chemistry, molecular structures
- **Biology**: Cell biology, genetics, ecology
- **Economics**: Microeconomics, game theory, market analysis

## Testing

### Quick Tests

```bash
# Run all tests
make test

# Simple functionality test
./test_simple.sh

# Domain-specific tests
./test_math_video.sh
./test_physics_video.sh
```

### Custom Test

```bash
# Create your own test
curl -X POST http://localhost:5001/v1/video/rendering \
  -H "Content-Type: application/json" \
  -d @your_test_config.json
```

## Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Start services
make docker-compose-up

# Stop services  
make docker-compose-down
```

### Manual Docker Build

```bash
# Build image
make docker-build

# Run container
make docker-run
```

## Project Structure

```
generative-manim-template/
├── api/                          # Flask API application
│   ├── routes/                   # API endpoints
│   │   ├── chat_generation.py    # Interactive chat interface
│   │   ├── code_generation.py    # Storyboard generation
│   │   └── video_rendering.py    # Video rendering engine
│   ├── utils/                    # Utility functions
│   │   ├── advanced_animations.py # Advanced Manim animations
│   │   └── storyboard.py         # Storyboard processing
│   ├── prompts/                  # AI prompts and templates
│   └── schemas/                  # JSON schemas for validation
├── config/                       # Configuration files
│   └── domains/                  # Domain-specific configurations
├── tests/                        # Test suite
├── media/                        # Generated video outputs
├── docs/                         # Documentation
├── Makefile                      # Development tasks
├── pyproject.toml               # Python package configuration
├── Dockerfile                   # Container configuration
└── docker-compose.yml           # Multi-container setup
```

## Configuration

### Aspect Ratios

- `16:9` - Standard widescreen (3840x2160, 30fps)
- `9:16` - Vertical/mobile (1080x1920, 30fps) 
- `1:1` - Square format (1080x1080, 30fps)

### Quality Settings

- `preview` - Fast generation (720p, 24fps)
- `high` - Production quality (1080p, 30fps)

### Supported Models

- **OpenAI**: `gpt-4o`, `o1-mini`
- **Anthropic**: `claude-3-5-sonnet`
- **DeepSeek**: `r1`

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/video/rendering` | POST | Generate video from text prompt |
| `/v1/chat/generation` | POST | Interactive chat with preview |
| `/v1/code/generation` | POST | Generate storyboard JSON |
| `/v1/video/exporting` | POST | Export and merge multiple videos |

## Advanced Features

### Custom Domain Configuration

Create a domain configuration file in `config/domains/your_domain.json`:

```json
{
  "name": "Mathematics",
  "persona": "You are an engaging mathematics educator",
  "topics": ["algebra", "calculus", "geometry"],
  "animation_style": "clean and mathematical",
  "color_scheme": {
    "primary": "#1E88E5",
    "secondary": "#FFC107"
  }
}
```

### Custom Animations

Add custom animations in `api/utils/custom_animations.py`:

```python
from manim import *

class CustomAnimation(Scene):
    def construct(self):
        # Your custom animation logic
        pass
```

## Development

### Setup Development Environment

```bash
# Install all development dependencies
make setup

# Run linting
make lint

# Format code
make format

# Run full CI pipeline
make all
```

### Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## Troubleshooting

### Common Issues

**Video Generation Fails**
```bash
# Check dependencies
make check

# Verify FFmpeg
ffmpeg -version

# Check LaTeX installation
pdflatex --version
```

**API Key Errors**
```bash
# Create .env file
make create-env

# Verify environment variables
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY
```

**Docker Issues**
```bash
# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Debug Mode

Enable verbose logging:
```bash
FLASK_DEBUG=1 python api/run.py
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Manim Community](https://www.manim.community/) - Mathematical animation engine
- [3Blue1Brown](https://www.3blue1brown.com/) - Inspiration for mathematical visualizations
- [OpenAI](https://openai.com/) & [Anthropic](https://anthropic.com/) - AI language models
- All contributors and users of this platform

## Support

For issues, questions, or contributions, please visit our [GitHub repository](https://github.com/rochmanofenna/Generative-Manim-Template).