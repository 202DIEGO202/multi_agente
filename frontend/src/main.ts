import { bootstrapApplication } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { App } from './app';
import { SectionLayout } from './shared/section-layout';

bootstrapApplication(App,{providers:[provideRouter([
  {path:'',pathMatch:'full',loadComponent:()=>import('./features/dashboard').then(m=>m.Dashboard)},
  {path:'',component:SectionLayout,data:{section:'workflow'},children:[
  {path:'workflow',loadComponent:()=>import('./features/workflow').then(m=>m.Workflow)},
  {path:'chat',loadComponent:()=>import('./features/chat').then(m=>m.Chat)},
  {path:'state',loadComponent:()=>import('./features/project-state').then(m=>m.ProjectStatePage)},
  {path:'backlog',loadComponent:()=>import('./features/backlog').then(m=>m.Backlog)},
  {path:'mockups',loadComponent:()=>import('./features/mockups').then(m=>m.Mockups)},
  {path:'architecture',loadComponent:()=>import('./features/architecture').then(m=>m.Architecture)},
  {path:'construction',loadComponent:()=>import('./features/construction').then(m=>m.Construction)},
  ]},
  {path:'',component:SectionLayout,data:{section:'resources'},children:[
  {path:'knowledge',loadComponent:()=>import('./features/knowledge').then(m=>m.Knowledge)},
  {path:'rag',loadComponent:()=>import('./features/observability').then(m=>m.Observability),data:{mode:'rag'}},
  {path:'activity',loadComponent:()=>import('./features/observability').then(m=>m.Observability),data:{mode:'monitor'}},
  ]},
  {path:'**',redirectTo:''}
])]}).catch(console.error);
