# Stage 1: Build
FROM node:18-alpine AS builder
WORKDIR /app

# Copiar package files primero (cache layer)
COPY package.json package-lock.json* ./
RUN npm ci --legacy-peer-deps

# Copiar fuente y buildear
COPY . .
RUN npm run build

# Stage 2: Serve con Nginx
FROM nginx:alpine

# Copiar el build output
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx config para SPA (React Router)
RUN cat > /etc/nginx/conf.d/default.conf << 'EOF'
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript;

    # Cache para assets estaticos
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # React Router — todas las rutas van a index.html
    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
