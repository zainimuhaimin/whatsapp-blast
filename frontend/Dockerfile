# Multi-stage build: build SPA dengan Node, sajikan via nginx.
FROM node:24-alpine AS build
WORKDIR /app

# Install dependencies dulu (cache layer)
COPY package.json package-lock.json ./
RUN npm ci

# Build
COPY . .
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Stage serve: nginx ringan
FROM nginx:1.27-alpine AS serve
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
