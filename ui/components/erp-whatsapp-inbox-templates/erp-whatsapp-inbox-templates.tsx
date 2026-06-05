import { Component, State, h } from '@stencil/core';
// Importa el DataTable compartido (Stencil) para que se auto-registre y esbuild
// lo empaquete dentro del bundle del módulo. El shell provee los `ion-*`.
import '../../../../_shared/ui/components/data-table/data-table';
import type { DataTableColumn } from '../../../../_shared/ui/components/data-table/data-table';

// Web Component del módulo `whatsapp_inbox` (Stencil). Vista "Templates": lista de
// plantillas de WhatsApp Business (aprobadas por Meta) + alta rápida. Es parte de la
// pieza `ui.entry` que el shell carga en runtime.
//
// La lógica vive en Rust: este componente NO toca la BD; llama al SDK
// (erplora.query/command/on). El listado usa el DataTable compartido + Ionic.

interface ErploraClientLike {
  query<T = unknown>(name: string, params?: Record<string, unknown>): Promise<T>;
  command<T = unknown>(name: string, payload?: Record<string, unknown>): Promise<T>;
  on(event: string, cb: (payload: unknown) => void): () => void;
}

interface Template {
  id: string;
  name: string;
  language: string;
  category: string;
  meta_status: string;
  is_active: number;
}

function erplora(): ErploraClientLike {
  const c = (globalThis as { erplora?: ErploraClientLike }).erplora;
  if (!c) throw new Error('erplora SDK no inicializado por el shell');
  return c;
}

@Component({
  tag: 'erp-whatsapp-inbox-templates',
  shadow: true,
  styles: `
    :host { display:block; font-family: system-ui, sans-serif; color: var(--ion-text-color, #1c1b18); }
    header { display:flex; gap:.5rem; align-items:center; margin-bottom:.75rem; }
    h2 { margin:0; font-size:1.15rem; flex:1; }
    .form { display:flex; gap:.5rem; flex-wrap:wrap; align-items:end; margin:.5rem 0 1rem; }
    .form ion-input, .form ion-select, .form ion-textarea { --background:var(--surface-2,#f7f4ec); border:1px solid var(--ion-border-color,#e0ddd4); border-radius:8px; min-width:8rem; }
    .err { color:#d9480f; font-weight:600; }
  `,
})
export class ErpWhatsappInboxTemplates {
  @State() templates: Template[] = [];
  @State() loading = true;
  @State() error = '';
  @State() newName = '';
  @State() newCategory = 'UTILITY';
  @State() newLanguage = 'es';
  @State() newBody = '';
  @State() saving = false;

  private unsub?: () => void;

  private columns: DataTableColumn[] = [
    { key: 'name', header: 'Nombre' },
    { key: 'language', header: 'Idioma' },
    { key: 'category', header: 'Categoría' },
    { key: 'meta_status', header: 'Estado Meta' },
    {
      key: 'is_active',
      header: 'Activa',
      align: 'right',
      format: (r) => (Number(r.is_active) ? 'Sí' : 'No'),
    },
  ];

  async componentWillLoad() {
    await this.refresh();
    try {
      const offs = [
        erplora().on('whatsapp_inbox.template.created', () => this.refresh()),
        erplora().on('whatsapp_inbox.template.updated', () => this.refresh()),
        erplora().on('whatsapp_inbox.template.deleted', () => this.refresh()),
      ];
      this.unsub = () => offs.forEach((o) => o());
    } catch {
      /* sin SDK (preview) → sin reactividad en vivo */
    }
  }

  disconnectedCallback() {
    this.unsub?.();
  }

  private async refresh() {
    this.loading = true;
    this.error = '';
    try {
      const rows = await erplora().query<Template[]>('whatsapp_inbox.templates.list', { active_only: 0 });
      this.templates = rows ?? [];
    } catch (e) {
      this.error = e instanceof Error ? e.message : 'Error cargando plantillas';
    } finally {
      this.loading = false;
    }
  }

  private async createTemplate(ev: Event) {
    ev.preventDefault();
    if (!this.newName.trim()) return;
    this.saving = true;
    this.error = '';
    try {
      await erplora().command('whatsapp_inbox.templates.create', {
        name: this.newName.trim(),
        language: this.newLanguage.trim() || 'es',
        category: this.newCategory,
        header: '',
        body: this.newBody,
        footer: '',
        variables: '[]',
      });
      this.newName = '';
      this.newBody = '';
      await this.refresh();
    } catch (e) {
      this.error = e instanceof Error ? e.message : 'No se pudo crear la plantilla';
    } finally {
      this.saving = false;
    }
  }

  render() {
    return (
      <div>
        <header>
          <h2>Plantillas WhatsApp</h2>
        </header>

        <form class="form" onSubmit={(e) => this.createTemplate(e)}>
          <ion-input
            placeholder="Nombre"
            value={this.newName}
            onIonInput={(e: any) => (this.newName = e.target.value)}
          />
          <ion-input
            placeholder="Idioma (es)"
            value={this.newLanguage}
            onIonInput={(e: any) => (this.newLanguage = e.target.value)}
          />
          <ion-select
            placeholder="Categoría…"
            value={this.newCategory}
            onIonChange={(e: any) => (this.newCategory = e.target.value)}
          >
            <ion-select-option value="UTILITY">Utility</ion-select-option>
            <ion-select-option value="MARKETING">Marketing</ion-select-option>
            <ion-select-option value="AUTHENTICATION">Authentication</ion-select-option>
          </ion-select>
          <ion-textarea
            placeholder="Cuerpo del mensaje"
            value={this.newBody}
            onIonInput={(e: any) => (this.newBody = e.target.value)}
          />
          <ion-button type="submit" size="small" disabled={this.saving || !this.newName}>
            {this.saving ? 'Guardando…' : 'Añadir'}
          </ion-button>
        </form>

        {this.error && <p class="err">{this.error}</p>}

        <data-table
          columns={this.columns}
          rows={this.templates as unknown as Record<string, unknown>[]}
          searchKeys={['name', 'category']}
          searchPlaceholder="Buscar nombre o categoría…"
          emptyMessage={this.loading ? 'Cargando…' : 'Sin plantillas.'}
        />
      </div>
    );
  }
}
