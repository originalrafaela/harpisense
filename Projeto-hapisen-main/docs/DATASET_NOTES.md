# Notas para o dataset ML

- Use sessões independentes; não divida registros da mesma sessão entre treino e teste.
- Não use `session_id`, IP específico, `ground_truth` ou nomes de cenário como feature.
- A03/A04 são predominantemente temporais: agregue em janelas (ex.: 5 s).
- A05 deve combinar log do broker com janela de rede; nunca armazene a senha tentada no dataset.
- A06/A07 dependem de ACL/auditoria; registre contagens de negações como contexto.
- A08 requer correlação entre principal autenticado, client ID, tópico e identidade declarada.
- A09 pode alimentar Random Forest e, de forma complementar, Isolation Forest.
