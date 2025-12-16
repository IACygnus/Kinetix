FROM node:18-alpine

WORKDIR /app

# Copiar package files
COPY package*.json ./

# Instalar dependencias
RUN npm install

# Copiar código
COPY . .

EXPOSE 5173

# Comando
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
