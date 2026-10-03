// O-3.6C: Operator 접근을 Cloudflare Access(이메일 인증) 대신 단순 비밀번호(HTTP Basic Auth)로
// 전환한다. Te가 대시보드에서 OPERATOR_PASSWORD 시크릿을 설정해야 동작한다.
// 설정 안 돼있으면(로컬 테스트 등) 전부 막는다 -- 평문 비밀번호 노출보다 접근 불가가 안전하다.

function unauthorized() {
  return new Response("Authentication required.", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="METAXIS Operator", charset="UTF-8"' },
  });
}

function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export default {
  async fetch(request, env) {
    if (!env.OPERATOR_PASSWORD) return unauthorized();

    const auth = request.headers.get("Authorization") || "";
    if (!auth.startsWith("Basic ")) return unauthorized();

    let decoded;
    try {
      decoded = atob(auth.slice(6));
    } catch {
      return unauthorized();
    }
    const sep = decoded.indexOf(":");
    const password = sep === -1 ? decoded : decoded.slice(sep + 1);
    if (!timingSafeEqual(password, env.OPERATOR_PASSWORD)) return unauthorized();

    return env.ASSETS.fetch(request);
  },
};
