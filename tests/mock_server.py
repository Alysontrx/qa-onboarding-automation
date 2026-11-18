"""Servidor HTTP de homologação mock para validação local do framework.

Permite testar fluxos completos de sucesso, validação e erro do formulário
de onboarding em ambiente isolado e sem dependências externas.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import sys

HTML_CONTENT = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Aplicação de Homologação - Onboarding</title>
  <style>
    body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; background: #f0f2f5; margin: 0; }
    .card { background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); width: 100%; max-width: 400px; }
    h2 { margin-top: 0; color: #1a73e8; }
    .form-group { margin-bottom: 1rem; }
    label { display: block; margin-bottom: 0.25rem; font-weight: bold; font-size: 0.9rem; }
    input { width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
    button { width: 100%; padding: 0.75rem; background: #1a73e8; color: white; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; }
    button:hover { background: #1557b0; }
    .success-msg { margin-top: 1rem; padding: 0.75rem; background: #e6f4ea; color: #137333; border-radius: 4px; font-weight: bold; }
    .error-msg { margin-top: 1rem; padding: 0.75rem; background: #fce8e6; color: #c5221f; border-radius: 4px; font-weight: bold; }
  </style>
</head>
<body>
  <div class="card">
    <h2>Cadastro de Usuário</h2>
    <form id="onboarding-form">
      <div class="form-group">
        <label for="name">Nome Completo</label>
        <input id="name" data-testid="input-name" name="name" type="text" required placeholder="Digite seu nome" />
      </div>
      <div class="form-group">
        <label for="email">E-mail</label>
        <input id="email" data-testid="input-email" name="email" type="email" required placeholder="exemplo@dominio.com" />
      </div>
      <div class="form-group">
        <label for="password">Senha</label>
        <input id="password" data-testid="input-password" name="password" type="password" required placeholder="Sua senha segura" />
      </div>
      <button data-testid="btn-submit" type="submit">Cadastrar</button>
    </form>
    <div id="feedback"></div>
  </div>

  <script>
    document.getElementById('onboarding-form').addEventListener('submit', function(e) {
      e.preventDefault();
      const email = document.querySelector('[data-testid="input-email"]').value;
      const feedback = document.getElementById('feedback');
      
      if (email.includes('falha') || email.includes('fail')) {
        feedback.innerHTML = '<div data-testid="error-message" class="error-msg">Erro: E-mail já registrado na base de dados.</div>';
      } else {
        feedback.innerHTML = '<div data-testid="success-message" class="success-msg">Sucesso: Cadastro concluído com êxito!</div>';
      }
    });
  </script>
</body>
</html>
"""


class MockHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_CONTENT.encode("utf-8"))

    def log_message(self, format, *args):
        # Silencia requisições normais no terminal
        pass


def run_mock_server(port: int = 8080):
    server = HTTPServer(("127.0.0.1", port), MockHandler)
    print(f"[*] Servidor de homologação mock rodando em http://127.0.0.1:{port}/register")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Servidor encerrado.")
        server.shutdown()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_mock_server(port)

