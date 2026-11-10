FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent ./agent

RUN useradd --create-home agentuser
USER agentuser

EXPOSE 8000
# Run with networking limited to the model API in production, and never give the container more secrets than OPENAI_API_KEY.
CMD ["uvicorn", "agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
