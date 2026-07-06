# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Stage 1: Build the React Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app
COPY ./frontend/package*.json ./
RUN npm ci
COPY ./frontend/ ./
RUN npm run build

# Stage 2: Package FastAPI Backend
FROM python:3.12-slim
RUN pip install --no-cache-dir uv==0.8.13
WORKDIR /code

# Copy python configs and install dependencies
COPY ./backend/pyproject.toml ./backend/README.md ./backend/uv.lock* ./
RUN uv sync --frozen

# Copy app code
COPY ./backend/app ./app

# Copy built static frontend files from Stage 1 to the backend static dir
COPY --from=frontend-builder /app/dist ./static

ARG COMMIT_SHA=""
ENV COMMIT_SHA=${COMMIT_SHA}

ARG AGENT_VERSION=0.0.0
ENV AGENT_VERSION=${AGENT_VERSION}

EXPOSE 8080
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
