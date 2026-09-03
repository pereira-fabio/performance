package com.performance.app.ui

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat

/*
 * The same palette the web dashboard uses, so the two halves of the app do not
 * look like different products. Values mirror the CSS custom properties in
 * frontend/src/index.css; changing one means changing both.
 */
private val Accent = Color(0xFFF2542D)
private val AccentDark = Color(0xFFFF6B41)

private val LightColors = lightColorScheme(
    primary = Accent,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFFEF1ED),
    onPrimaryContainer = Color(0xFF7A2412),
    background = Color(0xFFFFFFFF),
    onBackground = Color(0xFF18181B),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF18181B),
    surfaceVariant = Color(0xFFFAFAFA),
    onSurfaceVariant = Color(0xFF71717A),
    outline = Color(0xFFE4E4E7),
    outlineVariant = Color(0xFFD4D4D8),
    error = Color(0xFFDC2626),
)

private val DarkColors = darkColorScheme(
    primary = AccentDark,
    onPrimary = Color(0xFF1A0A05),
    primaryContainer = Color(0xFF2A1710),
    onPrimaryContainer = Color(0xFFFFCDBC),
    background = Color(0xFF0A0A0B),
    onBackground = Color(0xFFE4E4E7),
    surface = Color(0xFF0A0A0B),
    onSurface = Color(0xFFE4E4E7),
    surfaceVariant = Color(0xFF141416),
    onSurfaceVariant = Color(0xFF8B8B93),
    outline = Color(0xFF232326),
    outlineVariant = Color(0xFF2F2F34),
    error = Color(0xFFF87171),
)

private val AppTypography = Typography(
    titleLarge = TextStyle(fontSize = 20.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.3).sp),
    titleMedium = TextStyle(fontSize = 15.sp, fontWeight = FontWeight.SemiBold),
    bodyMedium = TextStyle(fontSize = 14.sp, lineHeight = 20.sp),
    bodySmall = TextStyle(fontSize = 12.sp, lineHeight = 17.sp),
    labelSmall = TextStyle(fontSize = 11.sp, fontWeight = FontWeight.Medium),
)

@Composable
fun PerformanceTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    val colors = if (dark) DarkColors else LightColors
    val view = LocalView.current

    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colors.background.toArgb()
            window.navigationBarColor = colors.background.toArgb()
            // Status-bar icons have to invert with the theme or they vanish
            // against their own background.
            WindowCompat.getInsetsController(window, view).apply {
                isAppearanceLightStatusBars = !dark
                isAppearanceLightNavigationBars = !dark
            }
        }
    }

    MaterialTheme(colorScheme = colors, typography = AppTypography, content = content)
}
