import { Component } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';
import { routes } from './routes';

// Shell común generado por la plantilla: navegación a partir de las rutas y el router-outlet.
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink],
  template: `
    <nav>
      @for (link of links; track link.path) {
        <a [routerLink]="link.path">{{ link.label }}</a>
      }
    </nav>
    <main><router-outlet /></main>
  `,
})
export class App {
  links = routes
    .filter((r) => !!r.path && !r.path.includes(':') && !r.path.includes('**'))
    .map((r) => ({ path: r.path as string, label: (r.data?.['label'] as string) ?? (r.path as string) }));
}

export { routes };
