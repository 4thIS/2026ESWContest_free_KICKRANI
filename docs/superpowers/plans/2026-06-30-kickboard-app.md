# KickboardApp 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ESP32-S3 장치와 WiFi로 통신하는 진동 측정 데이터 수집 Android 앱 구현

**Architecture:** 단일 Activity + Fragment 3개(메인/파일/설정) 구조. Navigation Component로 화면 전환, OkHttp로 HTTP 통신, FusedLocationProviderClient로 GPS 수집 후 세션 종료 시 일괄 전송. SharedPreferences로 장치 연결 정보 저장.

**Tech Stack:** Kotlin, XML Layout + ViewBinding, OkHttp 4.12, Navigation Component 2.7, Play Services Location 21.2, Coroutines 1.7, SharedPreferences

## Global Constraints

- minSdk: **API 29 (Android 10)** — WifiNetworkSpecifier 사용 요건
- targetSdk: API 34
- 패키지명: `com.vibrasoft.kickboardapp`
- 장치 기본 IP: `192.168.4.1`
- GPS 속도: FusedLocationClient는 m/s 반환 → `× 3.6` 변환해서 km/h로 사용
- `/speed-log` 전송 속도 단위: km/h (Float)
- 파일명 규칙: `{원본}_{노면종류}_{노면상태}.csv`
- 노면 종류 프리셋: `["아스팔트", "보도블럭", "콘크리트", "비포장", "기타"]`
- 노면 상태 프리셋: `["정상", "불량"]`

---

## 파일 구조

```
app/src/main/
├── AndroidManifest.xml
├── java/com/vibrasoft/kickboardapp/
│   ├── MainActivity.kt              — BottomNavigation 호스트
│   ├── data/
│   │   └── AppSettings.kt           — SharedPreferences 래퍼
│   ├── network/
│   │   └── DeviceApi.kt             — OkHttp HTTP 클라이언트
│   ├── gps/
│   │   └── GpsLogger.kt             — GPS 수집 및 포인트 누적
│   ├── wifi/
│   │   └── WifiConnector.kt         — WiFi AP 연결 요청
│   └── ui/
│       ├── MainFragment.kt          — 세션 제어 화면
│       ├── FileFragment.kt          — 파일 관리 화면
│       ├── FileAdapter.kt           — 파일 목록 RecyclerView 어댑터
│       └── SettingsFragment.kt      — 장치 설정 화면
└── res/
    ├── layout/
    │   ├── activity_main.xml        — BottomNavigationView + NavHostFragment
    │   ├── fragment_main.xml
    │   ├── fragment_file.xml
    │   ├── fragment_settings.xml
    │   └── item_file.xml            — 파일 목록 단일 아이템
    ├── menu/
    │   └── bottom_nav_menu.xml      — 하단 탭 3개
    └── navigation/
        └── nav_graph.xml            — Fragment 간 이동 그래프

app/src/test/java/com/vibrasoft/kickboardapp/
├── DeviceApiTest.kt                 — JSON 빌드 로직 단위 테스트
└── FileNameTest.kt                  — 파일명 생성 로직 단위 테스트
```

---

## Task 1: 프로젝트 생성 및 의존성 설정

**Files:**
- Create: `app/build.gradle.kts`
- Create: `app/src/main/AndroidManifest.xml`

**Interfaces:**
- Produces: 빌드 가능한 Android 프로젝트, 이후 모든 Task의 기반

- [ ] **Step 1: Android Studio에서 새 프로젝트 생성**

  Android Studio → New Project → Empty Views Activity 선택
  - Name: `KickboardApp`
  - Package name: `com.vibrasoft.kickboardapp`
  - Language: Kotlin
  - Minimum SDK: API 29

- [ ] **Step 2: `app/build.gradle.kts` 의존성 추가**

  `dependencies { }` 블록을 아래로 교체:

  ```kotlin
  dependencies {
      implementation("androidx.core:core-ktx:1.12.0")
      implementation("androidx.appcompat:appcompat:1.6.1")
      implementation("com.google.android.material:material:1.11.0")
      implementation("androidx.constraintlayout:constraintlayout:2.1.4")

      // Navigation Component
      implementation("androidx.navigation:navigation-fragment-ktx:2.7.7")
      implementation("androidx.navigation:navigation-ui-ktx:2.7.7")

      // OkHttp
      implementation("com.squareup.okhttp3:okhttp:4.12.0")

      // Coroutines
      implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

      // GPS
      implementation("com.google.android.gms:play-services-location:21.2.0")

      // RecyclerView
      implementation("androidx.recyclerview:recyclerview:1.3.2")

      testImplementation("junit:junit:4.13.2")
  }
  ```

  같은 파일 `android { }` 블록 안에 ViewBinding 활성화:

  ```kotlin
  android {
      // ... 기존 내용 유지 ...
      buildFeatures {
          viewBinding = true
      }
  }
  ```

- [ ] **Step 3: `AndroidManifest.xml` 권한 선언**

  `<manifest>` 태그 바로 아래, `<application>` 태그 위에 추가:

  ```xml
  <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
  <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
  <uses-permission android:name="android.permission.INTERNET" />
  <uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
  <uses-permission android:name="android.permission.CHANGE_WIFI_STATE" />
  <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
  <uses-permission android:name="android.permission.CHANGE_NETWORK_STATE" />
  ```

- [ ] **Step 4: 빌드 확인**

  ```
  ./gradlew assembleDebug
  ```

  Expected: `BUILD SUCCESSFUL`

- [ ] **Step 5: 커밋**

  ```bash
  git add .
  git commit -m "chore: 프로젝트 초기 설정 및 의존성 추가"
  ```

---

## Task 2: 네비게이션 셸 (MainActivity + 빈 Fragment 3개)

**Files:**
- Create: `res/menu/bottom_nav_menu.xml`
- Create: `res/navigation/nav_graph.xml`
- Create: `res/layout/activity_main.xml`
- Modify: `MainActivity.kt`
- Create: `res/layout/fragment_main.xml`
- Create: `res/layout/fragment_file.xml`
- Create: `res/layout/fragment_settings.xml`
- Create: `ui/MainFragment.kt`
- Create: `ui/FileFragment.kt`
- Create: `ui/SettingsFragment.kt`

**Interfaces:**
- Produces: 하단 탭으로 세 화면을 전환할 수 있는 앱 뼈대

- [ ] **Step 1: 하단 탭 메뉴 생성**

  `res/menu/bottom_nav_menu.xml` 생성:

  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <menu xmlns:android="http://schemas.android.com/apk/res/android">
      <item
          android:id="@+id/mainFragment"
          android:title="메인" />
      <item
          android:id="@+id/fileFragment"
          android:title="파일" />
      <item
          android:id="@+id/settingsFragment"
          android:title="설정" />
  </menu>
  ```

- [ ] **Step 2: 빈 Fragment 레이아웃 3개 생성**

  `res/layout/fragment_main.xml`:
  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
      android:layout_width="match_parent"
      android:layout_height="match_parent"
      android:orientation="vertical"
      android:gravity="center">
      <TextView android:layout_width="wrap_content"
          android:layout_height="wrap_content"
          android:text="메인 화면" />
  </LinearLayout>
  ```

  `res/layout/fragment_file.xml`:
  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
      android:layout_width="match_parent"
      android:layout_height="match_parent"
      android:orientation="vertical"
      android:gravity="center">
      <TextView android:layout_width="wrap_content"
          android:layout_height="wrap_content"
          android:text="파일 화면" />
  </LinearLayout>
  ```

  `res/layout/fragment_settings.xml`:
  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
      android:layout_width="match_parent"
      android:layout_height="match_parent"
      android:orientation="vertical"
      android:gravity="center">
      <TextView android:layout_width="wrap_content"
          android:layout_height="wrap_content"
          android:text="설정 화면" />
  </LinearLayout>
  ```

- [ ] **Step 3: Fragment 클래스 3개 생성**

  `ui/MainFragment.kt`:
  ```kotlin
  package com.vibrasoft.kickboardapp.ui

  import androidx.fragment.app.Fragment
  import com.vibrasoft.kickboardapp.R

  class MainFragment : Fragment(R.layout.fragment_main)
  ```

  `ui/FileFragment.kt`:
  ```kotlin
  package com.vibrasoft.kickboardapp.ui

  import androidx.fragment.app.Fragment
  import com.vibrasoft.kickboardapp.R

  class FileFragment : Fragment(R.layout.fragment_file)
  ```

  `ui/SettingsFragment.kt`:
  ```kotlin
  package com.vibrasoft.kickboardapp.ui

  import androidx.fragment.app.Fragment
  import com.vibrasoft.kickboardapp.R

  class SettingsFragment : Fragment(R.layout.fragment_settings)
  ```

- [ ] **Step 4: 네비게이션 그래프 생성**

  `res/navigation/nav_graph.xml`:
  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <navigation xmlns:android="http://schemas.android.com/apk/res/android"
      xmlns:app="http://schemas.android.com/apk/res-auto"
      android:id="@+id/nav_graph"
      app:startDestination="@id/mainFragment">

      <fragment
          android:id="@+id/mainFragment"
          android:name="com.vibrasoft.kickboardapp.ui.MainFragment"
          android:label="메인" />
      <fragment
          android:id="@+id/fileFragment"
          android:name="com.vibrasoft.kickboardapp.ui.FileFragment"
          android:label="파일" />
      <fragment
          android:id="@+id/settingsFragment"
          android:name="com.vibrasoft.kickboardapp.ui.SettingsFragment"
          android:label="설정" />
  </navigation>
  ```

- [ ] **Step 5: `activity_main.xml` 작성**

  기존 내용을 전부 교체:
  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
      xmlns:app="http://schemas.android.com/apk/res-auto"
      android:layout_width="match_parent"
      android:layout_height="match_parent"
      android:orientation="vertical">

      <androidx.fragment.app.FragmentContainerView
          android:id="@+id/nav_host_fragment"
          android:name="androidx.navigation.fragment.NavHostFragment"
          android:layout_width="match_parent"
          android:layout_height="0dp"
          android:layout_weight="1"
          app:defaultNavHost="true"
          app:navGraph="@navigation/nav_graph" />

      <com.google.android.material.bottomnavigation.BottomNavigationView
          android:id="@+id/bottom_nav"
          android:layout_width="match_parent"
          android:layout_height="wrap_content"
          app:menu="@menu/bottom_nav_menu" />
  </LinearLayout>
  ```

- [ ] **Step 6: `MainActivity.kt` 작성**

  ```kotlin
  package com.vibrasoft.kickboardapp

  import android.os.Bundle
  import androidx.appcompat.app.AppCompatActivity
  import androidx.navigation.fragment.NavHostFragment
  import androidx.navigation.ui.setupWithNavController
  import com.vibrasoft.kickboardapp.databinding.ActivityMainBinding

  class MainActivity : AppCompatActivity() {
      private lateinit var binding: ActivityMainBinding

      override fun onCreate(savedInstanceState: Bundle?) {
          super.onCreate(savedInstanceState)
          binding = ActivityMainBinding.inflate(layoutInflater)
          setContentView(binding.root)

          val navHost = supportFragmentManager
              .findFragmentById(R.id.nav_host_fragment) as NavHostFragment
          binding.bottomNav.setupWithNavController(navHost.navController)
      }
  }
  ```

- [ ] **Step 7: 앱 실행 후 수동 확인**

  에뮬레이터 또는 실기기에서 실행.
  확인: 하단 탭 3개가 보이고, 탭 전환 시 각 화면의 텍스트가 바뀌는지 확인.

- [ ] **Step 8: 커밋**

  ```bash
  git add .
  git commit -m "feat: 네비게이션 셸 구성 (MainActivity + Fragment 3개)"
  ```

---

## Task 3: AppSettings + SettingsFragment

**Files:**
- Create: `data/AppSettings.kt`
- Modify: `res/layout/fragment_settings.xml`
- Modify: `ui/SettingsFragment.kt`

**Interfaces:**
- Produces:
  - `AppSettings(context)` — SSID/비밀번호/IP 읽기·쓰기
  - `AppSettings.ssid: String`
  - `AppSettings.password: String`
  - `AppSettings.deviceIp: String`

- [ ] **Step 1: `AppSettings.kt` 작성**

  ```kotlin
  package com.vibrasoft.kickboardapp.data

  import android.content.Context

  class AppSettings(context: Context) {
      private val prefs = context.getSharedPreferences("device_settings", Context.MODE_PRIVATE)

      var ssid: String
          get() = prefs.getString("ssid", "VibraSafe_AP") ?: "VibraSafe_AP"
          set(value) { prefs.edit().putString("ssid", value).apply() }

      var password: String
          get() = prefs.getString("password", "") ?: ""
          set(value) { prefs.edit().putString("password", value).apply() }

      var deviceIp: String
          get() = prefs.getString("device_ip", "192.168.4.1") ?: "192.168.4.1"
          set(value) { prefs.edit().putString("device_ip", value).apply() }
  }
  ```

- [ ] **Step 2: `fragment_settings.xml` 작성**

  기존 내용을 전부 교체:
  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
      android:layout_width="match_parent"
      android:layout_height="match_parent"
      android:orientation="vertical"
      android:padding="24dp">

      <TextView android:layout_width="wrap_content"
          android:layout_height="wrap_content"
          android:text="장치 WiFi 설정"
          android:textSize="18sp"
          android:layout_marginBottom="24dp"/>

      <TextView android:layout_width="wrap_content"
          android:layout_height="wrap_content"
          android:text="SSID" />
      <EditText android:id="@+id/et_ssid"
          android:layout_width="match_parent"
          android:layout_height="wrap_content"
          android:inputType="text"
          android:layout_marginBottom="16dp"/>

      <TextView android:layout_width="wrap_content"
          android:layout_height="wrap_content"
          android:text="비밀번호" />
      <EditText android:id="@+id/et_password"
          android:layout_width="match_parent"
          android:layout_height="wrap_content"
          android:inputType="textPassword"
          android:layout_marginBottom="16dp"/>

      <TextView android:layout_width="wrap_content"
          android:layout_height="wrap_content"
          android:text="장치 IP" />
      <EditText android:id="@+id/et_ip"
          android:layout_width="match_parent"
          android:layout_height="wrap_content"
          android:inputType="text"
          android:layout_marginBottom="24dp"/>

      <Button android:id="@+id/btn_save"
          android:layout_width="match_parent"
          android:layout_height="wrap_content"
          android:text="저장" />
  </LinearLayout>
  ```

- [ ] **Step 3: `SettingsFragment.kt` 작성**

  ```kotlin
  package com.vibrasoft.kickboardapp.ui

  import android.os.Bundle
  import android.view.View
  import android.widget.Toast
  import androidx.fragment.app.Fragment
  import com.vibrasoft.kickboardapp.R
  import com.vibrasoft.kickboardapp.data.AppSettings
  import com.vibrasoft.kickboardapp.databinding.FragmentSettingsBinding

  class SettingsFragment : Fragment(R.layout.fragment_settings) {
      private var _binding: FragmentSettingsBinding? = null
      private val binding get() = _binding!!

      override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
          super.onViewCreated(view, savedInstanceState)
          _binding = FragmentSettingsBinding.bind(view)
          val settings = AppSettings(requireContext())

          // 저장된 값 불러오기
          binding.etSsid.setText(settings.ssid)
          binding.etPassword.setText(settings.password)
          binding.etIp.setText(settings.deviceIp)

          binding.btnSave.setOnClickListener {
              settings.ssid = binding.etSsid.text.toString().trim()
              settings.password = binding.etPassword.text.toString()
              settings.deviceIp = binding.etIp.text.toString().trim()
              Toast.makeText(requireContext(), "저장됨", Toast.LENGTH_SHORT).show()
          }
      }

      override fun onDestroyView() {
          super.onDestroyView()
          _binding = null
      }
  }
  ```

- [ ] **Step 4: 수동 확인**

  앱 실행 → 설정 탭 → SSID 입력 → 저장 → 앱 재실행 → 값이 유지되는지 확인.

- [ ] **Step 5: 커밋**

  ```bash
  git add .
  git commit -m "feat: AppSettings (SharedPreferences) + SettingsFragment"
  ```

---

## Task 4: DeviceApi (HTTP 통신)

**Files:**
- Create: `network/DeviceApi.kt`
- Create: `test/DeviceApiTest.kt`

**Interfaces:**
- Consumes: `AppSettings.deviceIp`
- Produces:
  - `DeviceApi(deviceIp: String)`
  - `suspend fun sync(timestamp: Long): Boolean`
  - `suspend fun start(): Boolean`
  - `suspend fun stop(): Boolean`
  - `suspend fun sendSpeedLog(points: List<GpsPoint>): Boolean`
  - `suspend fun getFiles(): List<String>`
  - `suspend fun renameFile(oldName: String, newName: String): Boolean`
  - `suspend fun addMemo(fileName: String, memo: String): Boolean`
  - `data class GpsPoint(val timestamp: Long, val speed: Float)` — 이 파일에 정의

- [ ] **Step 1: 단위 테스트 작성**

  `test/DeviceApiTest.kt`:
  ```kotlin
  package com.vibrasoft.kickboardapp

  import com.vibrasoft.kickboardapp.network.DeviceApi
  import com.vibrasoft.kickboardapp.network.GpsPoint
  import org.junit.Assert.assertEquals
  import org.junit.Test

  class DeviceApiTest {

      @Test
      fun buildSpeedLogJson_correctFormat() {
          val points = listOf(
              GpsPoint(1000L, 12.4f),
              GpsPoint(2000L, 13.1f)
          )
          val json = DeviceApi.buildSpeedLogJson(points)
          assertEquals(
              """[{"timestamp":1000,"speed":12.4},{"timestamp":2000,"speed":13.1}]""",
              json
          )
      }
  }
  ```

- [ ] **Step 2: 테스트 실패 확인**

  ```
  ./gradlew test
  ```

  Expected: FAIL — `DeviceApi`, `GpsPoint` 클래스 없음

- [ ] **Step 3: `DeviceApi.kt` 작성**

  ```kotlin
  package com.vibrasoft.kickboardapp.network

  import kotlinx.coroutines.Dispatchers
  import kotlinx.coroutines.withContext
  import okhttp3.MediaType.Companion.toMediaType
  import okhttp3.OkHttpClient
  import okhttp3.Request
  import okhttp3.RequestBody.Companion.toRequestBody
  import java.util.concurrent.TimeUnit

  data class GpsPoint(val timestamp: Long, val speed: Float)

  class DeviceApi(private val deviceIp: String) {
      private val client = OkHttpClient.Builder()
          .connectTimeout(5, TimeUnit.SECONDS)
          .readTimeout(10, TimeUnit.SECONDS)
          .build()

      private val baseUrl get() = "http://$deviceIp"
      private val json = "application/json".toMediaType()

      companion object {
          fun buildSpeedLogJson(points: List<GpsPoint>): String {
              val entries = points.joinToString(",") {
                  """{"timestamp":${it.timestamp},"speed":${it.speed}}"""
              }
              return "[$entries]"
          }
      }

      suspend fun sync(timestamp: Long): Boolean = post(
          "/sync", """{"timestamp":$timestamp}"""
      )

      suspend fun start(): Boolean = post("/start", "")

      suspend fun stop(): Boolean = post("/stop", "")

      suspend fun sendSpeedLog(points: List<GpsPoint>): Boolean = post(
          "/speed-log", buildSpeedLogJson(points)
      )

      suspend fun getFiles(): List<String> = withContext(Dispatchers.IO) {
          try {
              val request = Request.Builder().url("$baseUrl/files").get().build()
              client.newCall(request).execute().use { response ->
                  if (!response.isSuccessful) return@withContext emptyList()
                  val body = response.body?.string() ?: return@withContext emptyList()
                  // 응답 형식: ["file1.csv","file2.csv"]
                  body.trim('[', ']')
                      .split(",")
                      .map { it.trim().trim('"') }
                      .filter { it.endsWith(".csv") }
              }
          } catch (e: Exception) {
              emptyList()
          }
      }

      suspend fun renameFile(oldName: String, newName: String): Boolean = post(
          "/rename", """{"old":"$oldName","new":"$newName"}"""
      )

      suspend fun addMemo(fileName: String, memo: String): Boolean = post(
          "/memo", """{"file":"$fileName","memo":"$memo"}"""
      )

      private suspend fun post(path: String, bodyStr: String): Boolean =
          withContext(Dispatchers.IO) {
              try {
                  val body = bodyStr.toRequestBody(json)
                  val request = Request.Builder().url("$baseUrl$path").post(body).build()
                  client.newCall(request).execute().use { it.isSuccessful }
              } catch (e: Exception) {
                  false
              }
          }
  }
  ```

- [ ] **Step 4: 테스트 통과 확인**

  ```
  ./gradlew test
  ```

  Expected: `BUILD SUCCESSFUL`, `DeviceApiTest` PASS

- [ ] **Step 5: 커밋**

  ```bash
  git add .
  git commit -m "feat: DeviceApi (OkHttp) — 전체 엔드포인트 구현"
  ```

---

## Task 5: GpsLogger (GPS 수집)

**Files:**
- Create: `gps/GpsLogger.kt`
- Create: `test/FileNameTest.kt`

**Interfaces:**
- Produces:
  - `GpsLogger(context: Context)`
  - `fun start()` — GPS 수집 시작
  - `fun stop(): List<GpsPoint>` — 수집 중지 후 누적 포인트 반환 (리스트 초기화)
  - `var onSpeedUpdate: ((Float) -> Unit)?` — 속도 변경 시 콜백 (화면 갱신용)
  - `fun buildNewFileName(original: String, roadType: String, condition: String): String`

- [ ] **Step 1: 파일명 생성 단위 테스트 작성**

  `test/FileNameTest.kt`:
  ```kotlin
  package com.vibrasoft.kickboardapp

  import com.vibrasoft.kickboardapp.gps.GpsLogger
  import org.junit.Assert.assertEquals
  import org.junit.Test

  class FileNameTest {

      @Test
      fun buildNewFileName_appendsTypeAndCondition() {
          val result = GpsLogger.buildNewFileName(
              "20260630_143022.csv", "아스팔트", "불량"
          )
          assertEquals("20260630_143022_아스팔트_불량.csv", result)
      }

      @Test
      fun buildNewFileName_customType() {
          val result = GpsLogger.buildNewFileName(
              "20260630_143022.csv", "자갈길", "불량"
          )
          assertEquals("20260630_143022_자갈길_불량.csv", result)
      }
  }
  ```

- [ ] **Step 2: 테스트 실패 확인**

  ```
  ./gradlew test
  ```

  Expected: FAIL — `GpsLogger` 없음

- [ ] **Step 3: `GpsLogger.kt` 작성**

  ```kotlin
  package com.vibrasoft.kickboardapp.gps

  import android.annotation.SuppressLint
  import android.content.Context
  import android.os.Looper
  import com.google.android.gms.location.LocationCallback
  import com.google.android.gms.location.LocationRequest
  import com.google.android.gms.location.LocationResult
  import com.google.android.gms.location.LocationServices
  import com.google.android.gms.location.Priority
  import com.vibrasoft.kickboardapp.network.GpsPoint

  class GpsLogger(context: Context) {
      private val fusedClient = LocationServices.getFusedLocationProviderClient(context)
      private val points = mutableListOf<GpsPoint>()
      private var callback: LocationCallback? = null

      var onSpeedUpdate: ((Float) -> Unit)? = null

      companion object {
          fun buildNewFileName(original: String, roadType: String, condition: String): String {
              val base = original.removeSuffix(".csv")
              return "${base}_${roadType}_${condition}.csv"
          }
      }

      @SuppressLint("MissingPermission")
      fun start() {
          points.clear()
          val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 1000L)
              .setMinUpdateIntervalMillis(1000L)
              .build()
          callback = object : LocationCallback() {
              override fun onLocationResult(result: LocationResult) {
                  val loc = result.lastLocation ?: return
                  val speedKmh = loc.speed * 3.6f
                  points.add(GpsPoint(System.currentTimeMillis(), speedKmh))
                  onSpeedUpdate?.invoke(speedKmh)
              }
          }
          fusedClient.requestLocationUpdates(request, callback!!, Looper.getMainLooper())
      }

      fun stop(): List<GpsPoint> {
          callback?.let { fusedClient.removeLocationUpdates(it) }
          callback = null
          return points.toList().also { points.clear() }
      }
  }
  ```

- [ ] **Step 4: 테스트 통과 확인**

  ```
  ./gradlew test
  ```

  Expected: `BUILD SUCCESSFUL`, `FileNameTest` 2개 PASS

- [ ] **Step 5: 커밋**

  ```bash
  git add .
  git commit -m "feat: GpsLogger — GPS 수집 및 파일명 생성 유틸"
  ```

---

## Task 6: WifiConnector (WiFi AP 연결)

**Files:**
- Create: `wifi/WifiConnector.kt`

**Interfaces:**
- Consumes: `AppSettings.ssid`, `AppSettings.password`
- Produces:
  - `WifiConnector(context: Context)`
  - `fun connect(ssid: String, password: String, onResult: (Boolean) -> Unit)`
  - `fun disconnect()`

- [ ] **Step 1: `WifiConnector.kt` 작성**

  ```kotlin
  package com.vibrasoft.kickboardapp.wifi

  import android.content.Context
  import android.net.ConnectivityManager
  import android.net.Network
  import android.net.NetworkCapabilities
  import android.net.NetworkRequest
  import android.net.wifi.WifiNetworkSpecifier

  class WifiConnector(context: Context) {
      private val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
      private var networkCallback: ConnectivityManager.NetworkCallback? = null

      fun connect(ssid: String, password: String, onResult: (Boolean) -> Unit) {
          disconnect()

          val specBuilder = WifiNetworkSpecifier.Builder().setSsid(ssid)
          if (password.isNotEmpty()) specBuilder.setWpa2Passphrase(password)

          val request = NetworkRequest.Builder()
              .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
              .setNetworkSpecifier(specBuilder.build())
              .build()

          networkCallback = object : ConnectivityManager.NetworkCallback() {
              override fun onAvailable(network: Network) {
                  cm.bindProcessToNetwork(network)
                  onResult(true)
              }
              override fun onUnavailable() {
                  onResult(false)
              }
          }

          cm.requestNetwork(request, networkCallback!!)
      }

      fun disconnect() {
          networkCallback?.let {
              try { cm.unregisterNetworkCallback(it) } catch (_: Exception) {}
          }
          networkCallback = null
          cm.bindProcessToNetwork(null)
      }
  }
  ```

  > `cm.bindProcessToNetwork(network)` — 이 호출이 없으면 WiFi에 연결되어도 HTTP 요청이 셀룰러로 빠져나감.

- [ ] **Step 2: 빌드 확인**

  ```
  ./gradlew assembleDebug
  ```

  Expected: `BUILD SUCCESSFUL`

- [ ] **Step 3: 커밋**

  ```bash
  git add .
  git commit -m "feat: WifiConnector — AP 자동 연결 및 네트워크 바인딩"
  ```

---

## Task 7: MainFragment (세션 제어)

**Files:**
- Modify: `res/layout/fragment_main.xml`
- Modify: `ui/MainFragment.kt`

**Interfaces:**
- Consumes: `AppSettings`, `DeviceApi`, `GpsLogger`, `WifiConnector`
- Produces:
  - 세션 완료 시 `NavController`로 FileFragment 이동

- [ ] **Step 1: `fragment_main.xml` 작성**

  기존 내용을 전부 교체:
  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
      android:layout_width="match_parent"
      android:layout_height="match_parent"
      android:orientation="vertical"
      android:padding="24dp"
      android:gravity="center_horizontal">

      <!-- 연결 상태 -->
      <TextView android:id="@+id/tv_connection"
          android:layout_width="wrap_content"
          android:layout_height="wrap_content"
          android:text="○ 미연결"
          android:textSize="16sp"
          android:layout_marginBottom="8dp"/>

      <Button android:id="@+id/btn_connect"
          android:layout_width="match_parent"
          android:layout_height="wrap_content"
          android:text="WiFi 연결"
          android:layout_marginBottom="32dp"/>

      <!-- GPS 속도 -->
      <TextView android:id="@+id/tv_speed"
          android:layout_width="wrap_content"
          android:layout_height="wrap_content"
          android:text="0.0 km/h"
          android:textSize="48sp"
          android:layout_marginBottom="32dp"/>

      <!-- 세션 제어 버튼 -->
      <Button android:id="@+id/btn_sync"
          android:layout_width="match_parent"
          android:layout_height="wrap_content"
          android:text="시각 동기화"
          android:layout_marginBottom="8dp"/>

      <Button android:id="@+id/btn_session"
          android:layout_width="match_parent"
          android:layout_height="wrap_content"
          android:text="세션 시작"
          android:layout_marginBottom="32dp"/>

      <!-- 타이머 -->
      <TextView android:id="@+id/tv_timer"
          android:layout_width="wrap_content"
          android:layout_height="wrap_content"
          android:text="00:00:00"
          android:textSize="32sp"/>
  </LinearLayout>
  ```

- [ ] **Step 2: `MainFragment.kt` 작성**

  ```kotlin
  package com.vibrasoft.kickboardapp.ui

  import android.Manifest
  import android.content.pm.PackageManager
  import android.os.Bundle
  import android.view.View
  import androidx.activity.result.contract.ActivityResultContracts
  import androidx.core.content.ContextCompat
  import androidx.fragment.app.Fragment
  import androidx.lifecycle.lifecycleScope
  import androidx.navigation.fragment.findNavController
  import com.vibrasoft.kickboardapp.R
  import com.vibrasoft.kickboardapp.data.AppSettings
  import com.vibrasoft.kickboardapp.databinding.FragmentMainBinding
  import com.vibrasoft.kickboardapp.gps.GpsLogger
  import com.vibrasoft.kickboardapp.network.DeviceApi
  import com.vibrasoft.kickboardapp.wifi.WifiConnector
  import kotlinx.coroutines.Job
  import kotlinx.coroutines.delay
  import kotlinx.coroutines.launch

  class MainFragment : Fragment(R.layout.fragment_main) {
      private var _binding: FragmentMainBinding? = null
      private val binding get() = _binding!!

      private lateinit var settings: AppSettings
      private lateinit var api: DeviceApi
      private lateinit var gpsLogger: GpsLogger
      private lateinit var wifiConnector: WifiConnector

      private var isConnected = false
      private var isSessionRunning = false
      private var timerJob: Job? = null
      private var elapsedSeconds = 0L

      private val locationPermissionLauncher = registerForActivityResult(
          ActivityResultContracts.RequestMultiplePermissions()
      ) { grants ->
          if (grants.values.all { it }) startSession()
      }

      override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
          super.onViewCreated(view, savedInstanceState)
          _binding = FragmentMainBinding.bind(view)
          settings = AppSettings(requireContext())
          api = DeviceApi(settings.deviceIp)
          gpsLogger = GpsLogger(requireContext())
          wifiConnector = WifiConnector(requireContext())

          gpsLogger.onSpeedUpdate = { speed ->
              binding.tvSpeed.text = "%.1f km/h".format(speed)
          }

          binding.btnConnect.setOnClickListener { connectWifi() }
          binding.btnSync.setOnClickListener { syncTime() }
          binding.btnSession.setOnClickListener {
              if (isSessionRunning) stopSession() else checkPermissionAndStart()
          }

          updateButtonStates()
      }

      private fun connectWifi() {
          binding.tvConnection.text = "연결 중..."
          wifiConnector.connect(settings.ssid, settings.password) { success ->
              requireActivity().runOnUiThread {
                  isConnected = success
                  binding.tvConnection.text = if (success) "● 연결됨" else "○ 미연결"
                  updateButtonStates()
              }
          }
      }

      private fun syncTime() {
          lifecycleScope.launch {
              api.sync(System.currentTimeMillis())
          }
      }

      private fun checkPermissionAndStart() {
          val perms = arrayOf(
              Manifest.permission.ACCESS_FINE_LOCATION,
              Manifest.permission.ACCESS_COARSE_LOCATION
          )
          if (perms.all { ContextCompat.checkSelfPermission(requireContext(), it) == PackageManager.PERMISSION_GRANTED }) {
              startSession()
          } else {
              locationPermissionLauncher.launch(perms)
          }
      }

      private fun startSession() {
          lifecycleScope.launch {
              api.sync(System.currentTimeMillis())
              api.start()
              gpsLogger.start()
              isSessionRunning = true
              elapsedSeconds = 0L
              startTimer()
              updateButtonStates()
          }
      }

      private fun stopSession() {
          lifecycleScope.launch {
              api.stop()
              val points = gpsLogger.stop()
              api.sendSpeedLog(points)
              isSessionRunning = false
              timerJob?.cancel()
              updateButtonStates()
              findNavController().navigate(R.id.fileFragment)
          }
      }

      private fun startTimer() {
          timerJob?.cancel()
          timerJob = lifecycleScope.launch {
              while (true) {
                  delay(1000)
                  elapsedSeconds++
                  val h = elapsedSeconds / 3600
                  val m = (elapsedSeconds % 3600) / 60
                  val s = elapsedSeconds % 60
                  binding.tvTimer.text = "%02d:%02d:%02d".format(h, m, s)
              }
          }
      }

      private fun updateButtonStates() {
          binding.btnSync.isEnabled = isConnected && !isSessionRunning
          binding.btnSession.isEnabled = isConnected
          binding.btnSession.text = if (isSessionRunning) "세션 종료" else "세션 시작"
      }

      override fun onDestroyView() {
          super.onDestroyView()
          timerJob?.cancel()
          _binding = null
      }
  }
  ```

- [ ] **Step 3: 수동 확인**

  앱 실행 → 메인 탭에서 버튼 상태가 올바른지 확인:
  - 미연결 상태: 시각동기화·세션시작 비활성
  - WiFi 연결 후: 두 버튼 활성
  - 세션 시작 후: 타이머 카운트업, 버튼이 "세션 종료"로 전환

  > 실제 장치 없어도 버튼 상태 및 타이머 동작은 확인 가능.

- [ ] **Step 4: 커밋**

  ```bash
  git add .
  git commit -m "feat: MainFragment — 세션 제어 및 GPS 속도 표시"
  ```

---

## Task 8: FileFragment (파일 관리)

**Files:**
- Create: `res/layout/item_file.xml`
- Modify: `res/layout/fragment_file.xml`
- Create: `ui/FileAdapter.kt`
- Modify: `ui/FileFragment.kt`

**Interfaces:**
- Consumes: `DeviceApi.getFiles()`, `DeviceApi.renameFile()`, `DeviceApi.addMemo()`, `GpsLogger.buildNewFileName()`
- Produces: 파일 목록 표시 + 노면 유형 2단계 선택 후 이름 변경 + 메모 추가

- [ ] **Step 1: `item_file.xml` 작성**

  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
      android:layout_width="match_parent"
      android:layout_height="wrap_content"
      android:orientation="horizontal"
      android:padding="16dp">

      <TextView android:id="@+id/tv_file_name"
          android:layout_width="0dp"
          android:layout_height="wrap_content"
          android:layout_weight="1"
          android:textSize="14sp"/>

      <Button android:id="@+id/btn_rename"
          android:layout_width="wrap_content"
          android:layout_height="wrap_content"
          android:text="이름변경"
          android:textSize="12sp"/>

      <Button android:id="@+id/btn_memo"
          android:layout_width="wrap_content"
          android:layout_height="wrap_content"
          android:text="메모"
          android:textSize="12sp"
          android:layout_marginStart="8dp"/>
  </LinearLayout>
  ```

- [ ] **Step 2: `fragment_file.xml` 작성**

  기존 내용을 전부 교체:
  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
      android:layout_width="match_parent"
      android:layout_height="match_parent"
      android:orientation="vertical"
      android:padding="16dp">

      <LinearLayout
          android:layout_width="match_parent"
          android:layout_height="wrap_content"
          android:orientation="horizontal"
          android:layout_marginBottom="16dp">

          <TextView android:layout_width="0dp"
              android:layout_height="wrap_content"
              android:layout_weight="1"
              android:text="SD카드 파일 목록"
              android:textSize="18sp"/>

          <Button android:id="@+id/btn_refresh"
              android:layout_width="wrap_content"
              android:layout_height="wrap_content"
              android:text="새로고침"/>
      </LinearLayout>

      <androidx.recyclerview.widget.RecyclerView
          android:id="@+id/rv_files"
          android:layout_width="match_parent"
          android:layout_height="match_parent"/>
  </LinearLayout>
  ```

- [ ] **Step 3: `FileAdapter.kt` 작성**

  ```kotlin
  package com.vibrasoft.kickboardapp.ui

  import android.view.LayoutInflater
  import android.view.ViewGroup
  import androidx.recyclerview.widget.RecyclerView
  import com.vibrasoft.kickboardapp.databinding.ItemFileBinding

  class FileAdapter(
      private val files: MutableList<String>,
      private val onRename: (String) -> Unit,
      private val onMemo: (String) -> Unit
  ) : RecyclerView.Adapter<FileAdapter.ViewHolder>() {

      inner class ViewHolder(private val binding: ItemFileBinding) :
          RecyclerView.ViewHolder(binding.root) {

          fun bind(fileName: String) {
              binding.tvFileName.text = fileName
              binding.btnRename.setOnClickListener { onRename(fileName) }
              binding.btnMemo.setOnClickListener { onMemo(fileName) }
          }
      }

      override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
          val binding = ItemFileBinding.inflate(LayoutInflater.from(parent.context), parent, false)
          return ViewHolder(binding)
      }

      override fun onBindViewHolder(holder: ViewHolder, position: Int) {
          holder.bind(files[position])
      }

      override fun getItemCount() = files.size

      fun updateFiles(newFiles: List<String>) {
          files.clear()
          files.addAll(newFiles)
          notifyDataSetChanged()
      }

      fun renameFile(oldName: String, newName: String) {
          val idx = files.indexOf(oldName)
          if (idx >= 0) {
              files[idx] = newName
              notifyItemChanged(idx)
          }
      }
  }
  ```

- [ ] **Step 4: `FileFragment.kt` 작성**

  ```kotlin
  package com.vibrasoft.kickboardapp.ui

  import android.os.Bundle
  import android.view.View
  import android.widget.EditText
  import androidx.appcompat.app.AlertDialog
  import androidx.fragment.app.Fragment
  import androidx.lifecycle.lifecycleScope
  import androidx.recyclerview.widget.LinearLayoutManager
  import com.vibrasoft.kickboardapp.R
  import com.vibrasoft.kickboardapp.data.AppSettings
  import com.vibrasoft.kickboardapp.databinding.FragmentFileBinding
  import com.vibrasoft.kickboardapp.gps.GpsLogger
  import com.vibrasoft.kickboardapp.network.DeviceApi
  import kotlinx.coroutines.launch

  class FileFragment : Fragment(R.layout.fragment_file) {
      private var _binding: FragmentFileBinding? = null
      private val binding get() = _binding!!

      private lateinit var api: DeviceApi
      private lateinit var adapter: FileAdapter

      private val roadTypes = listOf("아스팔트", "보도블럭", "콘크리트", "비포장", "기타")
      private val roadConditions = listOf("정상", "불량")

      override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
          super.onViewCreated(view, savedInstanceState)
          _binding = FragmentFileBinding.bind(view)
          api = DeviceApi(AppSettings(requireContext()).deviceIp)

          adapter = FileAdapter(
              mutableListOf(),
              onRename = { fileName -> showRoadTypeDialog(fileName) },
              onMemo = { fileName -> showMemoDialog(fileName) }
          )
          binding.rvFiles.layoutManager = LinearLayoutManager(requireContext())
          binding.rvFiles.adapter = adapter

          binding.btnRefresh.setOnClickListener { loadFiles() }
          loadFiles()
      }

      private fun loadFiles() {
          lifecycleScope.launch {
              val files = api.getFiles()
              adapter.updateFiles(files)
          }
      }

      // 1단계: 노면 종류 선택
      private fun showRoadTypeDialog(fileName: String) {
          var selectedType = roadTypes[0]
          var customType = ""

          val dialog = AlertDialog.Builder(requireContext())
              .setTitle("노면 종류 선택")
              .setSingleChoiceItems(roadTypes.toTypedArray(), 0) { _, which ->
                  selectedType = roadTypes[which]
              }
              .setPositiveButton("다음") { _, _ ->
                  if (selectedType == "기타") {
                      showCustomTypeDialog(fileName)
                  } else {
                      showRoadConditionDialog(fileName, selectedType)
                  }
              }
              .setNegativeButton("취소", null)
              .create()
          dialog.show()
      }

      // 기타 선택 시 직접 입력
      private fun showCustomTypeDialog(fileName: String) {
          val input = EditText(requireContext()).apply { hint = "노면 종류 입력" }
          AlertDialog.Builder(requireContext())
              .setTitle("노면 종류 직접 입력")
              .setView(input)
              .setPositiveButton("다음") { _, _ ->
                  val custom = input.text.toString().trim()
                  if (custom.isNotEmpty()) showRoadConditionDialog(fileName, custom)
              }
              .setNegativeButton("취소", null)
              .show()
      }

      // 2단계: 노면 상태 선택
      private fun showRoadConditionDialog(fileName: String, roadType: String) {
          var selectedCondition = roadConditions[0]
          AlertDialog.Builder(requireContext())
              .setTitle("노면 상태 선택")
              .setSingleChoiceItems(roadConditions.toTypedArray(), 0) { _, which ->
                  selectedCondition = roadConditions[which]
              }
              .setPositiveButton("확인") { _, _ ->
                  renameFile(fileName, roadType, selectedCondition)
              }
              .setNegativeButton("뒤로") { _, _ ->
                  showRoadTypeDialog(fileName)
              }
              .show()
      }

      private fun renameFile(oldName: String, roadType: String, condition: String) {
          val newName = GpsLogger.buildNewFileName(oldName, roadType, condition)
          lifecycleScope.launch {
              val success = api.renameFile(oldName, newName)
              if (success) adapter.renameFile(oldName, newName)
          }
      }

      private fun showMemoDialog(fileName: String) {
          val input = EditText(requireContext()).apply { hint = "메모 입력" }
          AlertDialog.Builder(requireContext())
              .setTitle(fileName)
              .setView(input)
              .setPositiveButton("추가") { _, _ ->
                  val memo = input.text.toString().trim()
                  if (memo.isNotEmpty()) {
                      lifecycleScope.launch { api.addMemo(fileName, memo) }
                  }
              }
              .setNegativeButton("취소", null)
              .show()
      }

      override fun onDestroyView() {
          super.onDestroyView()
          _binding = null
      }
  }
  ```

- [ ] **Step 5: 빌드 및 수동 확인**

  ```
  ./gradlew assembleDebug
  ```

  Expected: `BUILD SUCCESSFUL`

  앱 실행 → 파일 탭에서:
  - 새로고침 버튼 탭 (장치 없으면 빈 목록 표시, 오류 없어야 함)
  - 이름변경 버튼 탭 → 1단계 다이얼로그 → "기타" 선택 시 입력창 → 2단계 다이얼로그 → 취소로 종료

- [ ] **Step 6: 커밋**

  ```bash
  git add .
  git commit -m "feat: FileFragment — 파일 목록, 2단계 노면 선택, 이름변경, 메모"
  ```

---

## Task 9: 전체 통합 테스트

**Files:**
- 수정 없음 — 통합 확인만

- [ ] **Step 1: 전체 단위 테스트 통과 확인**

  ```
  ./gradlew test
  ```

  Expected: `DeviceApiTest`, `FileNameTest` 모두 PASS

- [ ] **Step 2: 전체 사용자 흐름 수동 확인**

  에뮬레이터 또는 실기기:

  1. 설정 탭 → SSID/IP 입력 → 저장 → 앱 재실행 → 값 유지 확인
  2. 메인 탭 → 미연결 상태에서 시각동기화·세션시작 버튼 비활성 확인
  3. WiFi 연결 버튼 탭 → 시스템 연결 다이얼로그 팝업 확인 (연결 실패해도 OK)
  4. 연결된 척 버튼 활성 상태 확인 (또는 실제 AP가 있다면 연결 후 확인)
  5. 세션 시작 → GPS 권한 요청 팝업 확인 → 허용 → 타이머 카운트업 확인
  6. 세션 종료 → 파일 탭으로 자동 이동 확인
  7. 파일 탭 → 새로고침 → 이름변경 → 2단계 다이얼로그 흐름 확인

- [ ] **Step 3: 최종 커밋**

  ```bash
  git add .
  git commit -m "chore: 전체 통합 확인 완료"
  ```
