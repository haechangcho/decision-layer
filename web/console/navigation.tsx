// Adapt the shared Next pages to the packaged browser router.
import { Link as RouterLink, useLocation, useNavigate, useParams as routerParams } from "react-router-dom";
import type { AnchorHTMLAttributes } from "react";
export function usePathname() { return useLocation().pathname; }
export function useParams<T>() { return routerParams() as T; }
export function useRouter() {
  const navigate = useNavigate();
  return { push: (path: string) => navigate(path), replace: (path: string) => navigate(path, { replace: true }) };
}
export default function Link({ href, ...props }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) {
  return <RouterLink to={href} {...props} />;
}
