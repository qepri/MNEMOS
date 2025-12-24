# Stage 1: Build Angular app
FROM node:20-slim AS build

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build Angular app for production
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

# Copy built Angular app to nginx html directory
COPY --from=build /app/dist/frontend_theme3/browser /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
