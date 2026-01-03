"""
Ruta para generar certificado PDF de asignación de inventario corporativo
Agregar esta ruta a tu archivo de rutas principal (por ejemplo, reportes_routes.py o app.py)
"""

from flask import send_file, session
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from io import BytesIO
from datetime import datetime
import os

# Esta función debe agregarse a tu archivo de rutas de reportes
@app.route('/reportes/certificado/<int:asignacion_id>')
@login_required
def generar_certificado(asignacion_id):
    """
    Genera un certificado PDF para una asignación confirmada
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Obtener información completa de la asignación
        query = """
        SELECT 
            a.AsignacionId,
            a.FechaAsignacion,
            a.FechaConfirmacion,
            a.EstadoAsignacion,
            a.ObservacionesAsignacion,
            a.ObservacionesConfirmacion,
            p.ProductoId,
            p.NombreProducto,
            p.CodigoUnico,
            p.NumeroSerie,
            p.ValorCompra,
            p.Descripcion as DescripcionProducto,
            c.NombreCategoria,
            o.NombreOficina,
            o.Ciudad,
            o.Direccion,
            uad.UsuarioADId,
            uad.NombreCompleto as UsuarioNombre,
            uad.Email as UsuarioEmail,
            uad.Documento as UsuarioDocumento,
            uad.Cargo as UsuarioCargo,
            u_asigna.nombre as AsignadoPorNombre,
            u_asigna.email as AsignadoPorEmail,
            u_confirma.nombre as ConfirmadoPorNombre,
            u_confirma.email as ConfirmadoPorEmail
        FROM AsignacionesProducto a
        INNER JOIN Productos p ON a.ProductoId = p.ProductoId
        LEFT JOIN Categorias c ON p.CategoriaId = c.CategoriaId
        LEFT JOIN Oficinas o ON a.OficinaId = o.OficinaId
        LEFT JOIN UsuariosAD uad ON a.UsuarioADId = uad.UsuarioADId
        LEFT JOIN usuarios u_asigna ON a.AsignadoPor = u_asigna.id
        LEFT JOIN usuarios u_confirma ON a.ConfirmadoPor = u_confirma.id
        WHERE a.AsignacionId = ?
        """
        
        cursor.execute(query, (asignacion_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return "Asignación no encontrada", 404
        
        # Convertir a diccionario
        asignacion = dict(zip([column[0] for column in cursor.description], row))
        
        # Verificar permisos de acceso
        rol = session.get('rol')
        oficina_id = session.get('oficina_id')
        
        # Solo administradores, líderes de inventario o usuarios de la misma oficina pueden ver
        if rol not in ['administrador', 'lider_inventario']:
            if asignacion['OficinaId'] != oficina_id:
                conn.close()
                return "No tiene permisos para ver este certificado", 403
        
        conn.close()
        
        # Generar el PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, 
                              rightMargin=0.75*inch, leftMargin=0.75*inch,
                              topMargin=0.75*inch, bottomMargin=0.75*inch)
        
        # Contenedor de elementos
        elements = []
        
        # Estilos
        styles = getSampleStyleSheet()
        
        # Estilo personalizado para el título
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#0d6efd'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        # Estilo para subtítulos
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#198754'),
            spaceAfter=12,
            spaceBefore=20,
            fontName='Helvetica-Bold'
        )
        
        # Estilo para texto normal
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_JUSTIFY,
            spaceAfter=12
        )
        
        # ENCABEZADO
        elements.append(Spacer(1, 0.5*inch))
        
        # Título del certificado
        title = Paragraph("CERTIFICADO DE ASIGNACIÓN DE ACTIVO", title_style)
        elements.append(title)
        
        # Número de certificado y fecha
        cert_info = f"<b>Certificado No.:</b> {asignacion['AsignacionId']:06d} | <b>Fecha:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        elements.append(Paragraph(cert_info, normal_style))
        elements.append(Spacer(1, 0.3*inch))
        
        # INFORMACIÓN DEL COLABORADOR
        elements.append(Paragraph("INFORMACIÓN DEL COLABORADOR", subtitle_style))
        
        colaborador_data = [
            ['Nombre Completo:', asignacion['UsuarioNombre'] or 'N/A'],
            ['Documento:', asignacion['UsuarioDocumento'] or 'N/A'],
            ['Email:', asignacion['UsuarioEmail'] or 'N/A'],
            ['Cargo:', asignacion['UsuarioCargo'] or 'N/A'],
            ['Oficina:', f"{asignacion['NombreOficina']} - {asignacion['Ciudad']}" if asignacion['NombreOficina'] else 'N/A']
        ]
        
        colaborador_table = Table(colaborador_data, colWidths=[2*inch, 4.5*inch])
        colaborador_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e9ecef')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#212529')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ]))
        
        elements.append(colaborador_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # INFORMACIÓN DEL ACTIVO
        elements.append(Paragraph("INFORMACIÓN DEL ACTIVO", subtitle_style))
        
        activo_data = [
            ['Producto:', asignacion['NombreProducto'] or 'N/A'],
            ['Categoría:', asignacion['NombreCategoria'] or 'N/A'],
            ['Código Único:', asignacion['CodigoUnico'] or 'N/A'],
            ['Número de Serie:', asignacion['NumeroSerie'] or 'N/A'],
            ['Valor de Compra:', f"${asignacion['ValorCompra']:,.2f}" if asignacion['ValorCompra'] else 'N/A'],
        ]
        
        if asignacion['DescripcionProducto']:
            activo_data.append(['Descripción:', asignacion['DescripcionProducto']])
        
        activo_table = Table(activo_data, colWidths=[2*inch, 4.5*inch])
        activo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e9ecef')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#212529')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ]))
        
        elements.append(activo_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # INFORMACIÓN DE LA ASIGNACIÓN
        elements.append(Paragraph("INFORMACIÓN DE LA ASIGNACIÓN", subtitle_style))
        
        fecha_asignacion = asignacion['FechaAsignacion'].strftime('%d/%m/%Y %H:%M') if asignacion['FechaAsignacion'] else 'N/A'
        fecha_confirmacion = asignacion['FechaConfirmacion'].strftime('%d/%m/%Y %H:%M') if asignacion['FechaConfirmacion'] else 'N/A'
        
        asignacion_data = [
            ['Estado:', 'CONFIRMADO'],
            ['Fecha de Asignación:', fecha_asignacion],
            ['Asignado por:', asignacion['AsignadoPorNombre'] or 'N/A'],
            ['Fecha de Confirmación:', fecha_confirmacion],
            ['Confirmado por:', asignacion['ConfirmadoPorNombre'] or asignacion['UsuarioNombre'] or 'N/A'],
        ]
        
        asignacion_table = Table(asignacion_data, colWidths=[2*inch, 4.5*inch])
        asignacion_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e9ecef')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#212529')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ]))
        
        elements.append(asignacion_table)
        
        # OBSERVACIONES
        if asignacion['ObservacionesAsignacion'] or asignacion['ObservacionesConfirmacion']:
            elements.append(Spacer(1, 0.3*inch))
            elements.append(Paragraph("OBSERVACIONES", subtitle_style))
            
            obs_data = []
            if asignacion['ObservacionesAsignacion']:
                obs_data.append(['Asignación:', asignacion['ObservacionesAsignacion']])
            if asignacion['ObservacionesConfirmacion']:
                obs_data.append(['Confirmación:', asignacion['ObservacionesConfirmacion']])
            
            obs_table = Table(obs_data, colWidths=[2*inch, 4.5*inch])
            obs_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e9ecef')),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#212529')),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            elements.append(obs_table)
        
        # TÉRMINOS Y CONDICIONES
        elements.append(Spacer(1, 0.4*inch))
        elements.append(Paragraph("TÉRMINOS Y CONDICIONES", subtitle_style))
        
        terminos_text = """
        El colaborador se compromete a:
        <br/>• Hacer uso responsable del activo asignado.
        <br/>• Reportar inmediatamente cualquier daño, pérdida o mal funcionamiento.
        <br/>• Devolver el activo cuando sea requerido por la empresa o al finalizar la relación laboral.
        <br/>• No realizar modificaciones no autorizadas al equipo.
        <br/>• Mantener el activo en buenas condiciones de uso y funcionamiento.
        <br/><br/>
        La empresa se reserva el derecho de solicitar la devolución del activo en cualquier momento.
        El activo sigue siendo propiedad de la empresa y debe ser usado exclusivamente para fines laborales.
        """
        
        elements.append(Paragraph(terminos_text, normal_style))
        
        # PIE DE PÁGINA
        elements.append(Spacer(1, 0.5*inch))
        
        footer_text = f"""
        <br/><br/>
        _________________________________<br/>
        <b>{asignacion['UsuarioNombre']}</b><br/>
        {asignacion['UsuarioDocumento']}<br/>
        Firma del Colaborador
        """
        
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            alignment=TA_CENTER
        )
        
        elements.append(Paragraph(footer_text, footer_style))
        
        # Generar el PDF
        doc.build(elements)
        
        # Preparar para envío
        buffer.seek(0)
        
        # Nombre del archivo
        filename = f"Certificado_Asignacion_{asignacion['AsignacionId']:06d}_{asignacion['UsuarioNombre'].replace(' ', '_')}.pdf"
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"Error al generar certificado: {str(e)}")
        return f"Error al generar el certificado: {str(e)}", 500
