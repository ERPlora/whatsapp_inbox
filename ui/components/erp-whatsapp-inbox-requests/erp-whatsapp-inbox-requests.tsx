import { Component, State, h } from '@stencil/core';
// Importa el DataTable compartido (Stencil) para que se auto-registre y esbuild
// lo empaquete dentro del bundle del módulo. El shell provee los `ion-*`.
import '../../../../_shared/ui/components/data-table/data-table';
import type { DataTableColumn } from '../../../../_shared/ui/components/data-table/data-table';

// Web Component del módulo `whatsapp_inbox` (Stencil). Vista "Requests": lista de
// requests (pedidos/reservas/citas/presupuestos) extraídas por IA de las
// conversaciones, con acciones aprobar/rechazar. La transición fulfill (que crea el
// objeto enlazado en otro módulo) es un command WASM — ver WASM-TODO.md.
//
// La lógica vive en Rust: este componente NO toca la BD; llama al SDK
// (erplora.query/command/on). El listado usa el DataTable compartido + Ionic.

interface ErploraClientLike {
  query<T = unknown>(name: string, params?: Record<string, unknown>): Promise<T>;
  command<T = unknown>(name: string, payload?: Record<string, unknown>): Promise<T>;
  on(event: string, cb: (payload: unknown) => void): () => void;
}

interface InboxRequest {
  id: string;
  reference_number: string;
  request_type: string;
  status: string;
  contact_name: string;
  raw_summary: string;
  confidence_score: number;
  created_at: string;
}

function erplora(): ErploraClientLike {
  const c = (globalThis as { erplora?: ErploraClientLike }).erplora;
  if (!c) throw new Error('erplora SDK no inicializado por el shell');
  return c;
}

@Component({
  tag: 'erp-whatsapp-inbox-requests',
  shadow: true,
  styles: `
    :host { display:block; font-family: system-ui, sans-serif; color: var(--ion-text-color, #1c1b18); }
    header { display:flex; gap:.5rem; align-items:center; margin-bottom:.75rem; }
    h2 { margin:0; font-size:1.15rem; flex:1; }
    .filters { display:flex; gap:.5rem; flex-wrap:wrap; align-items:end; margin:.5rem 0 1rem; }
    .filters ion-select { --background:var(--surface-2,#f7f4ec); border:1px solid var(--ion-border-color,#e0ddd4); border-radius:8px; min-width:8rem; }
    .err { color:#d9480f; font-weight:600; }
    .actions { display:flex; gap:.35rem; }
  `,
})
export class ErpWhatsappInboxRequests {
  @State() requests: InboxRequest[] = [];
  @State() loading = true;
  @State() error = '';
  @State() status = '';
  @State() requestType = '';
  @State() busyId = '';

  private unsub?: () => void;

  private columns: DataTableColumn[] = [
    { key: 'reference_number', header: 'Referencia' },
    { key: 'request_type', header: 'Tipo' },
    { key: 'contact_name', header: 'Contacto' },
    { key: 'status', header: 'Estado' },
    {
      key: 'confidence_score',
      header: 'Confianza',
      align: 'right',
      format: (r) => `${Math.round((Number(r.confidence_score) || 0) * 100)}%`,
    },
    {
      key: 'id',
      header: 'Acciones',
      format: (r) => (r.status === 'pending_review' ? '⏳' : ''),
    },
  ];

  async componentWillLoad() {
    await this.refresh();
    try {
      const offs = [
        erplora().on('whatsapp_inbox.request.approved', () => this.refresh()),
        erplora().on('whatsapp_inbox.request.rejected', () => this.refresh()),
        erplora().on('whatsapp_inbox.request.fulfilled', () => this.refresh()),
        erplora().on('whatsapp_inbox.request.deleted', () => this.refresh()),
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
      const rows = await erplora().query<InboxRequest[]>('whatsapp_inbox.requests.list', {
        status: this.status,
        request_type: this.requestType,
      });
      this.requests = rows ?? [];
    } catch (e) {
      this.error = e instanceof Error ? e.message : 'Error cargando requests';
    } finally {
      this.loading = false;
    }
  }

  private async approve(id: string) {
    this.busyId = id;
    this.error = '';
    try {
      await erplora().command('whatsapp_inbox.requests.approve', { request_id: id });
      await this.refresh();
    } catch (e) {
      this.error = e instanceof Error ? e.message : 'No se pudo aprobar';
    } finally {
      this.busyId = '';
    }
  }

  private async reject(id: string) {
    this.busyId = id;
    this.error = '';
    try {
      await erplora().command('whatsapp_inbox.requests.reject', { request_id: id });
      await this.refresh();
    } catch (e) {
      this.error = e instanceof Error ? e.message : 'No se pudo rechazar';
    } finally {
      this.busyId = '';
    }
  }

  render() {
    const pending = this.requests.filter((r) => r.status === 'pending_review');
    return (
      <div>
        <header>
          <h2>Requests</h2>
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
            <ion-select-option value="pending_review">Pendientes</ion-select-option>
            <ion-select-option value="confirmed">Confirmadas</ion-select-option>
            <ion-select-option value="fulfilled">Cumplidas</ion-select-option>
            <ion-select-option value="rejected">Rechazadas</ion-select-option>
            <ion-select-option value="cancelled">Canceladas</ion-select-option>
          </ion-select>
          <ion-select
            placeholder="Tipo…"
            value={this.requestType}
            onIonChange={(e: any) => {
              this.requestType = e.target.value;
              this.refresh();
            }}
          >
            <ion-select-option value="">Todos</ion-select-option>
            <ion-select-option value="order">Pedido</ion-select-option>
            <ion-select-option value="reservation">Reserva</ion-select-option>
            <ion-select-option value="appointment">Cita</ion-select-option>
            <ion-select-option value="quote">Presupuesto</ion-select-option>
            <ion-select-option value="transport">Transporte</ion-select-option>
            <ion-select-option value="custom">Otro</ion-select-option>
          </ion-select>
        </div>

        {this.error && <p class="err">{this.error}</p>}

        {pending.length > 0 && (
          <div>
            <h3>Pendientes de revisión</h3>
            {pending.map((r) => (
              <div class="actions" key={r.id} style={{ margin: '.35rem 0' }}>
                <span style={{ flex: '1' }}>
                  {r.reference_number} · {r.request_type} · {r.contact_name}
                </span>
                <ion-button size="small" disabled={this.busyId === r.id} onClick={() => this.approve(r.id)}>
                  Aprobar
                </ion-button>
                <ion-button size="small" color="medium" disabled={this.busyId === r.id} onClick={() => this.reject(r.id)}>
                  Rechazar
                </ion-button>
              </div>
            ))}
          </div>
        )}

        <data-table
          columns={this.columns}
          rows={this.requests as unknown as Record<string, unknown>[]}
          searchKeys={['reference_number', 'contact_name', 'request_type']}
          searchPlaceholder="Buscar referencia o contacto…"
          emptyMessage={this.loading ? 'Cargando…' : 'Sin requests.'}
        />
      </div>
    );
  }
}
