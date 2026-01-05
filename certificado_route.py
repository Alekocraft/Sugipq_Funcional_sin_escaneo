"""
Blueprint para generar certificados PDF de asignación de inventario corporativo
con diseño Quálitas
MODIFICADO: Incluye número de identificación (cédula) en el certificado
"""

from flask import Blueprint, send_file, session
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.pdfgen import canvas as pdf_canvas
from io import BytesIO
from datetime import datetime
import os

# Importar funciones necesarias
from database import get_database_connection
from utils.auth import login_required

# Crear el Blueprint
certificado_bp = Blueprint('certificado', __name__, url_prefix='/reportes')

# Colores corporativos de Quálitas
QUALITAS_PURPLE = colors.HexColor('#7B2D8E')
QUALITAS_CYAN = colors.HexColor('#00B2E3')
QUALITAS_PINK = colors.HexColor('#E91E8C')
QUALITAS_GRAY = colors.HexColor('#58595B')

def add_header_footer(canvas, doc):
    """
    Función para agregar encabezado y pie de página con diseño Quálitas
    """
    canvas.saveState()
    
    # LOGO GRANDE QUE OCUPE TODA LA PARTE SUPERIOR
    logo_path = 'static/images/qualitas_logo.png'
    if os.path.exists(logo_path):
        try:
            # TAMAÑO MÁXIMO - que ocupe casi todo el ancho de la página
            logo_width = letter[0] - 1.5*inch  # Ancho de página menos márgenes
            logo_height = 1.2*inch  # Altura significativa
            
            # Centrar horizontalmente
            logo_x = (letter[0] - logo_width) / 2  # Centrado
            logo_y = letter[1] - 1.3*inch  # Posicionado en la parte superior
            
            canvas.drawImage(logo_path, logo_x, logo_y, 
                            width=logo_width, height=logo_height, 
                            preserveAspectRatio=True, mask='auto')
            
            print(f"✅ Logo dibujado: {logo_width:.2f} x {logo_height:.2f} pulgadas")
            print(f"✅ Posición: ({logo_x:.2f}, {logo_y:.2f})")
            
        except Exception as e:
            print(f"❌ No se pudo cargar el logo: {e}")
            # Dibujar rectángulo como fallback
            canvas.setFillColor(QUALITAS_PURPLE)
            canvas.rect(0.75*inch, letter[1] - 1.3*inch, letter[0] - 1.5*inch, 1.0*inch, fill=1)
            canvas.setFillColor(colors.white)
            canvas.setFont('Helvetica-Bold', 18)
            canvas.drawCentredString(letter[0]/2, letter[1] - 1.0*inch, "QUÁLITAS SEGUROS")
    
    # Línea decorativa inferior - más gruesa
    canvas.setStrokeColor(QUALITAS_PURPLE)
    canvas.setLineWidth(4)
    line_y = 0.5*inch
    canvas.line(0.5*inch, line_y, letter[0] - 0.5*inch, line_y)
    
    # Texto del pie de página
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(QUALITAS_GRAY)
    footer_text = "Para uso exclusivo de Quálitas Compañía de Seguros Colombia S.A. Prohibida la reproducción total o parcial de la información contenida en este documento."
    text_width = canvas.stringWidth(footer_text, 'Helvetica', 8)
    canvas.drawString((letter[0] - text_width) / 2, 0.3*inch, footer_text)
    
    canvas.restoreState()

@certificado_bp.route('/certificado/<int:asignacion_id>')
@login_required
def generar_certificado(asignacion_id):
    """
    Genera un certificado PDF para una asignación confirmada con diseño Quálitas
    MODIFICADO: Incluye número de identificación del usuario
    """
    
    # 🔍 PRINT DE DIAGNÓSTICO
    print("=" * 80)
    print("🎨 CÓDIGO NUEVO QUÁLITAS EJECUTÁNDOSE")
    print(f"📋 Generando certificado para asignación ID: {asignacion_id}")
    print("=" * 80)
    
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Obtener información completa de la asignación INCLUYENDO TOKEN Y NÚMERO DE IDENTIFICACIÓN
        query = """
        SELECT 
            a.AsignacionId,
            a.FechaAsignacion,
            a.FechaConfirmacion,
            a.Estado,
            a.Observaciones,
            p.ProductoId,
            p.NombreProducto,
            p.CodigoUnico,
            p.Descripcion,
            p.ValorUnitario,
            o.NombreOficina,
            o.Ubicacion,
            a.UsuarioADNombre,
            a.UsuarioADEmail,
            a.UsuarioAsignador,
            a.UsuarioConfirmacion,
            t.TokenId,
            t.TokenHash,
            t.UsuarioEmail AS TokenEmail,
            t.FechaCreacion AS TokenFechaCreacion,
            t.FechaExpiracion AS TokenFechaExpiracion,
            t.Utilizado AS TokenUtilizado,
            t.FechaUtilizacion AS TokenFechaUtilizacion,
            t.UsuarioConfirmacion AS TokenUsuarioConfirmacion,
            t.DireccionIP AS TokenDireccionIP,
            t.UserAgent AS TokenUserAgent,
            t.NumeroIdentificacion AS NumeroIdentificacion
        FROM Asignaciones a
        INNER JOIN ProductosCorporativos p ON a.ProductoId = p.ProductoId
        LEFT JOIN Oficinas o ON a.OficinaId = o.OficinaId
        LEFT JOIN TokensConfirmacionAsignacion t ON a.AsignacionId = t.AsignacionId
        WHERE a.AsignacionId = ? 
          AND UPPER(LTRIM(RTRIM(a.Estado))) = 'CONFIRMADO' 
          AND a.Activo = 1
        """
        
        cursor.execute(query, (asignacion_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            print("❌ Asignación no encontrada")
            return "Asignación no encontrada", 404
        
        # Convertir a diccionario
        asignacion = dict(zip([column[0] for column in cursor.description], row))
        
        # Verificar permisos de acceso
        rol = session.get('rol')
        oficina_id = session.get('oficina_id')
        
        # Solo administradores, líderes de inventario o usuarios de la misma oficina pueden ver
        if rol not in ['administrador', 'lider_inventario']:
            if asignacion.get('OficinaId') != oficina_id:
                conn.close()
                print("❌ Usuario sin permisos")
                return "No tiene permisos para ver este certificado", 403
        
        conn.close()
        
        print(f"✅ Datos obtenidos para: {asignacion.get('UsuarioADNombre', 'N/A')}")
        print(f"✅ Número de Identificación: {asignacion.get('NumeroIdentificacion', 'N/A')}")
        
        # Generar el PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=letter, 
            rightMargin=0.75*inch, 
            leftMargin=0.75*inch,
            topMargin=1.4*inch,  # Margen para el logo grande
            bottomMargin=0.75*inch
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Estilo para el título principal
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=QUALITAS_PURPLE,
            spaceAfter=8,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        # Estilo para subtítulos
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=QUALITAS_PURPLE,
            spaceAfter=8,
            spaceBefore=8,
            fontName='Helvetica-Bold',
            borderWidth=0,
            borderColor=QUALITAS_PURPLE,
            borderPadding=4,
            backColor=colors.HexColor('#F8F9FA')
        )
        
        # Estilo para texto normal
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_JUSTIFY,
            textColor=QUALITAS_GRAY,
            leading=14
        )
        
        # ========== TÍTULO PRINCIPAL ==========
        elements.append(Paragraph("CERTIFICADO DE ASIGNACIÓN DE ACTIVO CORPORATIVO", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # ========== INFORMACIÓN DEL USUARIO ==========
        elements.append(Paragraph("INFORMACIÓN DEL COLABORADOR", subtitle_style))
        
        # INCLUIR NÚMERO DE IDENTIFICACIÓN EN LA INFORMACIÓN DEL USUARIO
        numero_identificacion = asignacion.get('NumeroIdentificacion', 'N/A')
        
        usuario_data = [
            ['Nombre Completo:', asignacion.get('UsuarioADNombre', 'N/A')],
            ['Número de Identificación:', numero_identificacion],  # NUEVO CAMPO
            ['Correo Electrónico:', asignacion.get('UsuarioADEmail', 'N/A')],
            ['Oficina:', asignacion.get('NombreOficina', 'N/A')],
            ['Ubicación:', asignacion.get('Ubicacion', 'N/A')]
        ]
        
        usuario_table = Table(usuario_data, colWidths=[2.2*inch, 4.3*inch])
        usuario_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8F9FA')),
            ('TEXTCOLOR', (0, 0), (0, -1), QUALITAS_PURPLE),
            ('TEXTCOLOR', (1, 0), (1, -1), QUALITAS_GRAY),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DEE2E6')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(usuario_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # ========== INFORMACIÓN DEL ACTIVO ==========
        elements.append(Paragraph("INFORMACIÓN DEL ACTIVO ASIGNADO", subtitle_style))
        
        activo_data = [
            ['Nombre del Producto:', asignacion.get('NombreProducto', 'N/A')],
            ['Código Único:', asignacion.get('CodigoUnico', 'N/A')],
            ['Descripción:', asignacion.get('Descripcion', 'N/A') or 'Sin descripción'],
            ['Valor Estimado:', f"${asignacion.get('ValorUnitario', 0):,.2f} COP" if asignacion.get('ValorUnitario') else 'N/A']
        ]
        
        activo_table = Table(activo_data, colWidths=[2.2*inch, 4.3*inch])
        activo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8F9FA')),
            ('TEXTCOLOR', (0, 0), (0, -1), QUALITAS_PURPLE),
            ('TEXTCOLOR', (1, 0), (1, -1), QUALITAS_GRAY),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DEE2E6')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(activo_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # ========== DETALLES DE LA ASIGNACIÓN ==========
        elements.append(Paragraph("DETALLES DE LA ASIGNACIÓN", subtitle_style))
        
        fecha_asignacion = asignacion['FechaAsignacion'].strftime('%d/%m/%Y %H:%M') if asignacion.get('FechaAsignacion') else 'N/A'
        fecha_confirmacion = asignacion['FechaConfirmacion'].strftime('%d/%m/%Y %H:%M') if asignacion.get('FechaConfirmacion') else 'N/A'
        fecha_utilizacion_token = asignacion['TokenFechaUtilizacion'].strftime('%d/%m/%Y %H:%M:%S') if asignacion.get('TokenFechaUtilizacion') else 'N/A'
        
        asignacion_data = [
            ['Estado:', 'CONFIRMADO'],
            ['Fecha de Asignación:', fecha_asignacion],
            ['Asignado por:', asignacion.get('UsuarioAsignador', 'N/A')],
            ['Fecha de Confirmación:', fecha_confirmacion],
            ['Confirmado por:', asignacion.get('UsuarioConfirmacion') or asignacion.get('UsuarioADNombre', 'N/A')],
            ['Cédula del Confirmador:', numero_identificacion],  # NUEVO CAMPO
            ['Token de Confirmación:', f"Hash: {asignacion.get('TokenHash', 'N/A')[:20]}..." if asignacion.get('TokenHash') else 'N/A'],
            ['Fecha Utilización Token:', fecha_utilizacion_token],
            ['IP de Confirmación:', asignacion.get('TokenDireccionIP', 'N/A')],
        ]
        
        asignacion_table = Table(asignacion_data, colWidths=[2.2*inch, 4.3*inch])
        asignacion_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8F9FA')),
            ('TEXTCOLOR', (0, 0), (0, -1), QUALITAS_PURPLE),
            ('TEXTCOLOR', (1, 0), (1, -1), QUALITAS_GRAY),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DEE2E6')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(asignacion_table)
        
        # ========== OBSERVACIONES ==========
        if asignacion.get('Observaciones'):
            elements.append(Spacer(1, 0.2*inch))
            elements.append(Paragraph("OBSERVACIONES", subtitle_style))
            
            obs_data = [['Observaciones:', asignacion.get('Observaciones', '')]]
            
            obs_table = Table(obs_data, colWidths=[2.2*inch, 4.3*inch])
            obs_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8F9FA')),
                ('TEXTCOLOR', (0, 0), (0, -1), QUALITAS_PURPLE),
                ('TEXTCOLOR', (1, 0), (1, -1), QUALITAS_GRAY),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DEE2E6')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            elements.append(obs_table)
        
        # ========== TÉRMINOS Y CONDICIONES ==========
        elements.append(Spacer(1, 0.25*inch))
        elements.append(Paragraph("TÉRMINOS Y CONDICIONES", subtitle_style))
        
        terminos_text = """
        El colaborador se compromete a:
        • Hacer uso responsable y apropiado del activo asignado exclusivamente para actividades laborales.
        • Reportar inmediatamente cualquier daño, pérdida, robo o mal funcionamiento del equipo.
        • Devolver el activo cuando sea requerido por la empresa o al finalizar la relación laboral.
        • No realizar modificaciones, reparaciones o instalaciones no autorizadas al equipo.
        • Mantener el activo en buenas condiciones de uso, funcionamiento y seguridad.
        • Cumplir con las políticas de seguridad de la información de la empresa.
        La empresa se reserva el derecho de:
        • Solicitar la devolución del activo en cualquier momento.
        • Realizar inspecciones periódicas del estado y uso del activo.
        • Aplicar las sanciones correspondientes en caso de uso indebido o daño por negligencia.
        
        El activo permanece como propiedad de la empresa y debe ser utilizado exclusivamente para fines laborales.
        La pérdida, daño o uso indebido del activo podrá generar responsabilidades económicas y/o disciplinarias
        según lo establecido en el reglamento interno de trabajo.
        """
        
        elements.append(Paragraph(terminos_text, normal_style))
        
        # ========== FIRMA ELECTRÓNICA ==========
        elements.append(Spacer(1, 0.3*inch))
        
        # Información de validación de firma electrónica según TOKEN
        fecha_hora_actual = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        
        # Determinar quién confirmó (basado en token o asignación)
        usuario_confirmacion = asignacion.get('TokenUsuarioConfirmacion') or asignacion.get('UsuarioConfirmacion') or asignacion.get('UsuarioADNombre', 'N/A')
        email_confirmacion = asignacion.get('TokenEmail', asignacion.get('UsuarioADEmail', 'N/A'))
        
        firma_data = [
            [asignacion.get('UsuarioADNombre', 'N/A'), usuario_confirmacion],
            ['Colaborador Receptor', 'Colaborador Confirmador'],
            [f"Fecha Recepción: {fecha_asignacion}", f"Fecha Confirmación: {fecha_utilizacion_token if fecha_utilizacion_token != 'N/A' else fecha_confirmacion}"],
            [f"Email: {asignacion.get('UsuarioADEmail', 'N/A')}", f"Email: {email_confirmacion}"],
            [f"CC: {numero_identificacion}", f"Token ID: {asignacion.get('TokenId', 'N/A')}"],
        ]
        
        firma_table = Table(firma_data, colWidths=[3.25*inch, 3.25*inch])
        firma_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), QUALITAS_GRAY),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(firma_table)
        
        # ========== VALIDACIÓN DE FIRMA ELECTRÓNICA ==========
        elements.append(Spacer(1, 0.15*inch))
        
        validacion_text = f"""
        Validación de Firma Electrónica:
        • Token de confirmación generado: {asignacion.get('TokenFechaCreacion').strftime('%d/%m/%Y %H:%M:%S') if asignacion.get('TokenFechaCreacion') else 'N/A'}
        • Hash del token: {asignacion.get('TokenHash', 'N/A')}
        • Número de Identificación del confirmador: {numero_identificacion}
        • Este certificado ha sido firmado electrónicamente mediante el sistema de gestión de inventario de Quálitas.
        • La firma electrónica tiene validez legal conforme a la Ley 527 de 1999 de Colombia.
        • Documento generado automáticamente por el sistema el {fecha_hora_actual}
        """
        
        elements.append(Paragraph(validacion_text, ParagraphStyle(
            'ValidacionStyle',
            parent=styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER,
            spaceAfter=5,
            textColor=QUALITAS_GRAY,
            leading=10
        )))
        
        # ========== AUTORIZACIÓN DE DATOS PERSONALES ==========
        elements.append(Spacer(1, 0.15*inch))
        
        autorizacion_text = """
        AUTORIZACIÓN DE TRATAMIENTO DE DATOS PERSONALES:
        El colaborador autoriza de manera previa, expresa e informada el tratamiento de sus datos personales 
        (incluyendo su número de identificación), para fines de manejo de activos de la compañía 
        Quálitas Compañía de Seguros Colombia S.A. Declara que conoce su derecho a conocer, actualizar y 
        rectificar su información, conforme a la Política de Tratamiento de Datos disponible en 
        https://www.qualitascolombia.com.co/politica-de-seguridad
        """
        
        elements.append(Paragraph(autorizacion_text, ParagraphStyle(
            'AutorizacionStyle',
            parent=styles['Normal'],
            fontSize=7,
            alignment=TA_JUSTIFY,
            spaceAfter=5,
            textColor=QUALITAS_GRAY,
            leading=9,
            leftIndent=20,
            rightIndent=20,
            backColor=colors.HexColor('#F8F9FA'),
            borderWidth=1,
            borderColor=QUALITAS_PURPLE,
            borderPadding=10
        )))
        
        # Generar el PDF con encabezado y pie de página
        doc.build(elements, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
        
        buffer.seek(0)
        
        # Nombre del archivo
        nombre_usuario = asignacion.get('UsuarioADNombre', 'Usuario').replace(' ', '_')
        nombre_archivo = f"Certificado_Asignacion_{asignacion['AsignacionId']:06d}_{nombre_usuario}.pdf"
        
        print(f"✅ Certificado generado exitosamente: {nombre_archivo}")
        print("=" * 80)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=nombre_archivo
        )
        
    except Exception as e:
        print(f"❌ ERROR al generar certificado: {str(e)}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return f"Error al generar el certificado: {str(e)}", 500