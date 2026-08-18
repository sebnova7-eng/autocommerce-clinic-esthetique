"""
AutoCommerce Clinic — Générateur PDF (Factures et Devis)
Utilise ReportLab pour générer des documents professionnels.
"""
import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from models.database import Facture, Patient


async def generate_invoice_pdf(facture: Facture, patient: Patient, clinic: dict) -> bytes:
    """Génère un PDF pour une facture ou un devis."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    
    elements = []
    
    # Header
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Heading1'], alignment=1, fontSize=20, spaceAfter=20)
    title = "FACTURE" if facture.statut != "brouillon" else "DEVIS"
    elements.append(Paragraph(f"{title} - {facture.numero_facture}", header_style))
    
    # Infos Clinique & Patient
    info_data = [
        [Paragraph(f"<b>Émetteur :</b><br/>{clinic.get('clinic_name', 'AutoCommerce Clinic')}<br/>{clinic.get('address', '')}<br/>{clinic.get('phone', '')}", styles['Normal']),
         Paragraph(f"<b>Client :</b><br/>{patient.prenom} {patient.nom}<br/>{patient.adresse or ''}<br/>{patient.telephone}", styles['Normal'])]
    ]
    info_table = Table(info_data, colWidths=[8*cm, 8*cm])
    info_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    elements.append(info_table)
    elements.append(Spacer(1, 1*cm))
    
    # Infos Facture
    elements.append(Paragraph(f"Date d'émission : {facture.date_emission}", styles['Normal']))
    if facture.date_echeance:
        elements.append(Paragraph(f"Date d'échéance : {facture.date_echeance}", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))
    
    # Tableau des lignes
    table_data = [['Description', 'Prix Unitaire', 'Qté', 'Total HT']]
    
    lignes = (facture.actes or []) + (facture.produits or [])
    for ligne in lignes:
        prix = Decimal(str(ligne.get('prix', 0)))
        qte = int(ligne.get('quantite', 1))
        total_ligne = prix * qte
        table_data.append([
            ligne.get('description', 'Sans description'),
            f"{prix:.2f} DT",
            str(qte),
            f"{total_ligne:.2f} DT"
        ])
    
    # Totaux
    table_data.append(['', '', 'Sous-total HT', f"{facture.sous_total:.2f} DT"])
    if facture.remise_globale_pct > 0:
        remise_montant = facture.sous_total * (facture.remise_globale_pct / Decimal("100"))
        table_data.append(['', '', f"Remise ({facture.remise_globale_pct}%)", f"-{remise_montant:.2f} DT"])
    
    tva_pct = (facture.taux_tva * 100).quantize(Decimal("1"))
    table_data.append(['', '', f"TVA ({tva_pct}%)", f"{facture.montant_tva:.2f} DT"])
    table_data.append(['', '', 'TOTAL TTC', f"{facture.total_ttc:.2f} DT"])
    
    items_table = Table(table_data, colWidths=[9*cm, 3*cm, 1*cm, 3*cm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (0,1), (0,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,-1), (-1,-1), colors.lightgrey),
        ('GRID', (0,0), (-1,-5), 1, colors.black),
        ('LINEBELOW', (2,-4), (-1,-1), 1, colors.black),
        ('FONTNAME', (2,-1), (-1,-1), 'Helvetica-Bold'),
    ]))
    elements.append(items_table)
    
    # Notes
    if facture.notes:
        elements.append(Spacer(1, 1*cm))
        elements.append(Paragraph("<b>Notes :</b>", styles['Normal']))
        elements.append(Paragraph(facture.notes, styles['Normal']))
        
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
