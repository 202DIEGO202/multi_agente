import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

export const adminGuard: CanActivateFn = () => {
  const router = inject(Router);
  const token = sessionStorage.getItem('admin_token');
  if (!token) {
    return router.parseUrl('/acceso');
  }
  return true;
};