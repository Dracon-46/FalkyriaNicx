"""Conta Falkyria (opcional): login, perfil, backup criptografado e LGPD.

O Nicx funciona inteiro sem conta. Com ela, dá para guardar um backup dos
assistentes, rotinas, habilidades, pacotes e servidores MCP (sem segredos),
cifrado no PC com uma senha que só a pessoa sabe, e restaurar em outro PC.

- :mod:`cofre`: a sessão no PC (protegida pelo Windows com DPAPI);
- :mod:`cliente`: o Supabase Auth e o banco da Falkyria;
- :mod:`cripto`: scrypt + AES-256-GCM do backup;
- :mod:`backup`: o que entra no backup e como volta;
- :mod:`servico`: o que a tela e as rotas usam.
"""
