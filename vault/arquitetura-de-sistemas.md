---
title: Arquitetura de Sistemas
tags: [arquitetura, engenharia, sistemas]
---

# Arquitetura de Sistemas

## Principios

- **Separacao de responsabilidades**: Cada modulo tem uma funcao clara
- **Baixo acoplamento**: Modulos independentes entre si
- **Alta coesao**: Elementos relacionados agrupados juntos

## Padroes Comuns

### Microservicos
Arquitetura onde o sistema e dividido em servicos pequenos e independentes.

### Event-Driven
Comunicacao entre componentes via eventos asincronos.

### API Gateway
Ponto unico de entrada para todos os servicos. Veja [[Conceitos de IA]] para entender como a IA se integra nessa arquitetura.

## Stack Tecnologica

- **Backend**: Python, FastAPI, Node.js
- **Frontend**: React, Vue, Vanilla JS
- **Database**: PostgreSQL, SQLite, MongoDB
- **Cache**: Redis
- **Message Queue**: RabbitMQ, Kafka

## Integracoes com IA

Para integrar IA nos sistemas, e importante entender [[Prompt Engineering]] e como fornecer contexto adequado para os modelos.
