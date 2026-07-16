# Como Publicar uma Atualização — Mercearia Godoi PDV
=====================================================

## Formato do Sistema de Atualização

O PDV verifica automaticamente novas versões no repositório:
  https://github.com/Nomade04/PDV

A verificação ocorre toda vez que o sistema é iniciado.

---

## Passo a Passo para Publicar uma Atualização

### 1. Prepare os arquivos atualizados
Coloque todos os arquivos `.py` que foram modificados numa pasta.
Exemplo:
```
minha_atualizacao/
  ├── interface.py       (se mudou)
  ├── clientes.py        (se mudou)
  ├── vendas_interface.py (se mudou)
  └── ...
```

### 2. Crie o arquivo update.zip
Compacte APENAS os arquivos `.py` que mudaram num arquivo chamado:
  **update.zip**

⚠️ O arquivo DEVE se chamar exatamente `update.zip`.
⚠️ Coloque os arquivos .py diretamente na raiz do ZIP (sem subpastas).

### 3. Crie uma Release no GitHub
1. Acesse: https://github.com/Nomade04/PDV/releases/new
2. Em **Tag version**: coloque a nova versão (ex: `v1.1.0`)
   - Use o formato: vMAJOR.MINOR.PATCH
   - Exemplos: v1.0.1 (correção), v1.1.0 (melhoria), v2.0.0 (grande mudança)
3. Em **Release title**: coloque um nome descritivo (ex: "Versão 1.1.0 - Melhorias no PDV")
4. Em **Description**: descreva o que mudou (aparece no popup do sistema)
5. Em **Attach binaries**: arraste o arquivo `update.zip`
6. Clique em **Publish release**

### 4. O sistema atualiza automaticamente
Na próxima vez que o PDV for iniciado:
- O sistema detecta a versão nova (v1.1.0 > v1.0.0)
- Exibe um popup perguntando se quer atualizar
- Se confirmar, baixa o update.zip e aplica os arquivos
- Salva a nova versão em versao.txt

---

## Versionamento Semântico

| Tipo de mudança | Exemplo |
|----------------|---------|
| Correção de bug pequeno | v1.0.0 → v1.0.1 |
| Nova funcionalidade | v1.0.1 → v1.1.0 |
| Mudança grande/incompatível | v1.1.0 → v2.0.0 |

---

## Arquivos do Sistema de Atualização

| Arquivo | Função |
|---------|--------|
| `updater.py` | Lógica de verificação e aplicação |
| `versao.txt` | Versão instalada atualmente |
| `update_log.txt` | Log de atualizações realizadas |

---

## Notas Importantes

- O sistema **não reinicia automaticamente** após a atualização
- Reinicie o PDV manualmente após atualizar para carregar os novos arquivos
- O updater faz backup automático dos arquivos antes de substituir
- Se a atualização falhar, os arquivos originais são mantidos