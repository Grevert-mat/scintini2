# Karaokê YouTube - TODO

## Banco de Dados e Autenticação
- [x] Definir schema de salas/sessões de karaokê
- [x] Definir schema de fila de músicas
- [x] Definir schema de histórico de reprodução
- [x] Integração com YouTube OAuth para autenticação
- [x] Sistema de tokens YouTube para evitar comerciais

## YouTube API e Busca
- [x] Configurar YouTube Data API v3
- [x] Implementar busca de vídeos com "karaoke" automático
- [x] Cache de resultados de busca
- [x] Validação de vídeos de karaokê

## WebSocket e Sincronização em Tempo Real
- [x] Configurar Socket.IO para comunicação em tempo real
- [x] Sistema de salas/conexões WebSocket
- [x] Sincronização de estado do player
- [x] Sincronização de fila de músicas
- [x] Notificações de mudanças em tempo real

## Interface de Exibição Principal
- [x] Layout da tela principal (full-screen ready)
- [x] Integração do YouTube IFrame Player
- [x] Controles de reprodução (play, pause, skip)
- [x] Exibição da música atual
- [x] Exibição da próxima música na fila
- [x] Indicador de conexão e sincronização

## Interface Mobile
- [x] Layout responsivo para celular
- [x] Barra de busca com autocomplete
- [x] Exibição da fila de músicas
- [x] Botões de controle (play, pause, skip, remove)
- [x] Código/ID da sala para compartilhamento
- [x] Indicador de conexão

## Fila de Músicas e Sincronização
- [x] Adicionar música à fila
- [x] Remover música da fila
- [x] Reordenar fila
- [x] Sincronização automática entre dispositivos
- [x] Persistência de fila no banco de dados

## Testes e Validação
- [ ] Testes de autenticação YouTube
- [ ] Testes de sincronização WebSocket
- [ ] Testes de busca de karaokês
- [ ] Testes de fila de músicas
- [ ] Testes de responsividade mobile

## Deploy e Documentação
- [ ] Documentação de setup
- [ ] Guia de uso para usuários
- [ ] Variáveis de ambiente necessárias

## Bugs Encontrados e Corrigidos
- [x] Erro ao buscar música ao entrar em sala - adicionado melhor tratamento de erro com console.error
- [x] Quem cria a sala não consegue buscar músicas - redirecionado para Remote automaticamente
- [x] Melhorar fluxo: criador da sala agora pode buscar/adicionar músicas sem sair
- [x] Erro "Erro ao buscar músicas" - corrigido import de Zod no arquivo karaoke.ts

## Bugs Novos para Corrigir
- [ ] Erro ao buscar músicas ainda persiste - investigar causa raiz
- [ ] Adicionar botão/modal de logs para mostrar erros detalhados ao usuário
- [ ] Melhorar tratamento de erro com mensagens mais descritivas
