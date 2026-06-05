import { Component, State, h } from '@stencil/core';
// Importa el DataTable compartido (Stencil) para que se auto-registre y esbuild
// lo empaquete dentro del bundle del módulo. El shell provee los `ion-*`.
import '../../../../_shared/ui/components/data-table/data-table';
import type { DataTableColumn } from '../../../../_shared/ui/components/data-table/data-table';

// Web Component del módulo `whatsapp_inbox` (Stencil). Vista "Inbox": lista de
// conversaciones de WhatsApp + filtro por estado + búsqueda por contacto +
// reasignación de empleado. Es parte de la pieza `ui.entry` que el shell carga en
// runtime (modules/whatsapp_inbox/dist/whatsapp_inbox.esm.js).
//
// La lógica vive en Rust: este componente NO toca la BD; llama al SDK
// (erplora.query/command/on). El listado usa el DataTable compartido + Ionic.

interface ErploraClientLike {
  query<T = unknown>(name: string, params?: Record<string, unknown>): Promise<T>;
  command<T = unknown>(name: string, payload?: Record<string, unknown>): Promise<T>;
  on(event: string, cb: (payload: unknown) => void): () => void;
}

interface Conversation {
  id: string;
  contact_name: string;
  contact_phone: string;
  status: string;
  unread_count: number;
  assigned_to_id: string | null;
  last_message_at: string | null;
}

function erplora(): ErploraClientLike {
  const c = (globalThis as { erplora?: ErploraClientLike }).erplora;
  if (!c) throw new Error('erplora SDK no inicializado por el shell');
  return c;
}

@Component({
  tag: 'erp-whatsapp-inbox-inbox',
  shadow: true,
  styles: `
    :host { display:block; font-family: system-ui, sans-serif; color: var(--ion-text-color, #1c1b18); }
    header { display:flex; gap:.5rem; align-items:center; margin-bottom:.75rem; }
    h2 { margin:0; font-size:1.15rem; flex:1; }
    .filters { display:flex; gap:.5rem; flex-wrap:wrap; align-items:end; margin:.5rem 0 1rem; }
    .filters ion-input, .filters ion-select { --background:var(--surface-2,#f7f4ec); border:1px solid var(--ion-border-color,#e0ddd4); border-radius:8px; min-width:8rem; }
    .err { color:#d9480f; font-weight:600; }
    .unread { color:#1971c2; font-weight:700; }
  `,
})
export class ErpWhatsappInboxInbox {
  @State() conversations: Conversation[] = [];
  @State() loading = true;
  @State() error = '';
  @State() status = '';
  @State() search = '';

  private unsub?: () => void;

  private columns: DataTableColumn[] = [
    { key: 'contact_name', header: 'Contacto' },
    { key: 'contact_phone', header: 'Teléfono' },
    { key: 'status', header: 'Estado' },
    {
      key: 'unread_count',
      header: 'Sin leer',
      align: 'right',
      format: (r) => (Number(r.unread_count) > 0 ? String(r.unread_count) : '—'),
    },
    { key: 'last_message_at', header: 'Último mensaje' },
  ];

  async componentWillLoad() {
    await this.refresh();
    try {
      const off1 = erplora().on('whatsapp_inbox.conversation.assigned', () => this.refresh());
      this.unsub = () => off1();
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
      const rows = await erplora().query<Conversation[]>('whatsapp_inbox.conversations.list', {
        status: this.status,
        assigned_to_id: '',
        search: this.search.trim(),
      });
      this.conversations = rows ?? [];
    } catch (e) {
      this.error = e instanceof Error ? e.message : 'Error cargando conversaciones';
    } finally {
      this.loading = false;
    }
  }

  render() {
    return (
      <div>
        <header>
          <h2>Inbox WhatsApp</h2>
        </header>

        <div class="filters">
          <ion-select
            placeholder="Estado…"
            value={this.status}
            onIonChange={(e: any) => {
              this.status = e.target.value;
              this.refresh();
            }}
          >
            <ion-select-option value="">Todos</ion-select-option>
            <ion-select-option value="active">Activas</ion-select-option>
            <ion-select-option value="closed">Cerradas</ion-select-option>
          </ion-select>
          <ion-input
            placeholder="Buscar contacto…"
            value={this.search}
            onIonInput={(e: any) => (this.search = e.target.value)}
          />
          <ion-button size="small" onClick={() => this.refresh()}>
            Buscar
          </ion-button>
        </div>

        {this.error && <p class="err">{this.error}</p>}

        <data-table
          columns={this.columns}
          rows={this.conversations as unknown as Record<string, unknown>[]}
          searchKeys={['contact_name', 'contact_phone']}
          searchPlaceholder="Filtrar contacto o teléfono…"
          emptyMessage={this.loading ? 'Cargando…' : 'Sin conversaciones.'}
        />
      </div>
    );
  }
}
