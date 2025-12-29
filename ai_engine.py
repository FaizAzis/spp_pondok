import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier

class AIEngine:
    def __init__(self, df_payment, df_master):
        # Konversi tanggal agar aman digunakan oleh .dt accessor
        if not df_payment.empty:
            df_payment['tanggal_bayar'] = pd.to_datetime(df_payment['tanggal_bayar'], errors='coerce')
        self.df = df_payment
        self.df_m = df_master
        self.threshold = 0.6 # Default threshold

    def get_financial_metrics(self):
        """Menghitung metrik dasar keuangan"""
        if self.df.empty: return None
        total_tagihan = self.df['tagihan_wajib'].sum()
        total_masuk = self.df['nominal_bayar'].sum()
        total_sisa = self.df['sisa_tagihan'].sum()
        
        return {
            "rate": round((total_masuk / total_tagihan * 100), 1) if total_tagihan > 0 else 0,
            "tunggakan": int(total_sisa),
            "telat_count": len(self.df[self.df['keterangan'] == "Telat Bayar"])
        }

    def run_random_forest_analysis(self):
        """Logika Machine Learning untuk klasifikasi risiko"""
        if self.df.empty or len(self.df['nis'].unique()) < 2: return None
        
        # Agregasi data untuk fitur ML
        data = self.df.groupby('nis').agg({
            'nominal_bayar': 'mean',
            'sisa_tagihan': 'sum',
            'keterangan': lambda x: (x == 'Telat Bayar').sum()
        }).reset_index()
        
        data['target'] = (data['sisa_tagihan'] > 0).astype(int)
        
        # Fitur X dan Target y
        X = data[['nominal_bayar', 'sisa_tagihan', 'keterangan']]
        y = data['target']
        
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X, y)
        
        # Ambil probabilitas risiko
        data['risk_score'] = model.predict_proba(X)[:, 1]
        data['risk_level'] = data['risk_score'].apply(
            lambda x: "Tinggi" if x >= self.threshold else ("Sedang" if x > 0.3 else "Rendah")
        )
        
        return data.merge(self.df_m[['nis', 'nama']], on='nis')