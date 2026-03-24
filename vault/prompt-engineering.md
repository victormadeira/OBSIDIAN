---
title: Prompt Engineering
tags: [ia, prompts, engenharia]
---

# Prompt Engineering

A arte de estruturar instrucoes para obter melhores resultados de [[Conceitos de IA|modelos de IA]].

## Tecnicas

### Few-Shot Learning
Fornecer exemplos no prompt para guiar o modelo:

```
Exemplo: "Gato" -> Animal
Exemplo: "Carro" -> Veiculo
Pergunta: "Mesa" -> ?
```

### Chain of Thought
Pedir ao modelo que raciocine passo a passo antes de responder.

### System Prompts
Definir o comportamento e personalidade do modelo no inicio da conversa.

## Contexto e Knowledge Base

O **OBSIDIAN** foi criado exatamente para isso: construir uma base de conhecimento estruturada que pode ser exportada como contexto para modelos de IA.

### Como usar com IA

1. Documente conhecimento relevante em notas
2. Conecte notas com `[[links]]` semanticos
3. Use o **Construtor de Contexto** para selecionar notas relevantes
4. Exporte em formato XML (recomendado para Claude)
5. Inclua o contexto no system prompt da IA

Isso permite que a IA tenha acesso a informacoes estruturadas e relacionadas, melhorando significativamente a qualidade das respostas.

Veja: [[Conceitos de IA]] | [[Arquitetura de Sistemas]] | [[Bem-vindo ao OBSIDIAN]]
