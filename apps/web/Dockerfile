FROM node:20-alpine

WORKDIR /app

# Install dependencies (cached unless package-lock.json changes)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source (will be overridden by volume mount in dev)
COPY . .

CMD ["npm", "run", "dev"]
