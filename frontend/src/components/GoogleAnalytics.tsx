import Script from "next/script"

// Google Analytics 4 con Consent Mode: la medición arranca sin cookies de analítica
// (analytics_storage "denied") y solo las activa si el visitante aceptó en el banner de
// cookies. CookieBanner actualiza el consentimiento cuando elige.
export const GA_ID = "G-X99R9JK4MD"
export const CLAVE_CONSENTIMIENTO = "gobernia-cookie-consent"

export default function GoogleAnalytics() {
  return (
    <>
      <Script src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`} strategy="afterInteractive" />
      <Script id="google-analytics" strategy="afterInteractive">
        {`window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
var consentimiento = null;
try { consentimiento = localStorage.getItem("${CLAVE_CONSENTIMIENTO}"); } catch (e) {}
gtag("consent", "default", {
  ad_storage: "denied", ad_user_data: "denied", ad_personalization: "denied",
  analytics_storage: consentimiento === "accepted" ? "granted" : "denied"
});
gtag("js", new Date());
gtag("config", "${GA_ID}");`}
      </Script>
    </>
  )
}
