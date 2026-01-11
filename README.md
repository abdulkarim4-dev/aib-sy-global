export default function AIBSYMarketplace() { return ( <div className="min-h-screen bg-gray-50 p-6"> {/* Header */} <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-center md:justify-between"> <div className="flex items-center gap-2 text-2xl font-bold"> <Car className="h-8 w-8" /> <span>AIB-SY GLOBAL</span> </div> <nav className="flex flex-wrap gap-4 text-sm"> <a href="#" className="hover:underline">الرئيسية</a> <a href="#" className="hover:underline">السيارات</a> <a href="#" className="hover:underline">القصّات</a> <a href="#" className="hover:underline">المحركات</a> <a href="#" className="hover:underline">قطع التبديل</a> <a href="#" className="hover:underline">تواصل معنا</a> </nav> </header>

{/* Intro */}
  <section className="mb-8">
    <h1 className="mb-2 text-3xl font-semibold">منصة AIB-SY الدولية</h1>
    <p className="max-w-4xl text-gray-600">
      سوق دولي لبيع وشراء السيارات، القصّات، المحركات وقطع التبديل، مصمم بأسلوب احترافي مشابه لـ Autoline مع دعم التصدير والاستيراد.
    </p>
  </section>

  {/* Advanced Global Search */}
  <section className="mb-10 grid grid-cols-1 gap-4 rounded-2xl bg-white p-6 shadow md:grid-cols-3 lg:grid-cols-6">
    <Input placeholder="بحث عالمي (اسم، موديل، كود إعلان)" />

    <Select>
      <SelectTrigger><SelectValue placeholder="فئة المركبة" /></SelectTrigger>
      <SelectContent>
        <SelectItem value="sedan">سيارات سيدان</SelectItem>
        <SelectItem value="truck">شاحنات</SelectItem>
        <SelectItem value="construction">معدات بناء</SelectItem>
        <SelectItem value="agriculture">معدات زراعية</SelectItem>
        <SelectItem value="engine">محركات</SelectItem>
        <SelectItem value="parts">قطع التبديل</SelectItem>
      </SelectContent>
    </Select>

    <Select>
      <SelectTrigger><SelectValue placeholder="الدولة" /></SelectTrigger>
      <SelectContent>
        <SelectItem value="kr">كوريا</SelectItem>
        <SelectItem value="jp">اليابان</SelectItem>
        <SelectItem value="de">ألمانيا</SelectItem>
        <SelectItem value="tr">تركيا</SelectItem>
        <SelectItem value="us">أمريكا</SelectItem>
      </SelectContent>
    </Select>

    <Select>
      <SelectTrigger><SelectValue placeholder="الشركة" /></SelectTrigger>
      <SelectContent>
        <SelectItem value="hyundai">Hyundai</SelectItem>
        <SelectItem value="kia">Kia</SelectItem>
        <SelectItem value="volvo">Volvo</SelectItem>
        <SelectItem value="caterpillar">Caterpillar</SelectItem>
        <SelectItem value="john">John Deere</SelectItem>
      </SelectContent>
    </Select>

    <Select>
      <SelectTrigger><SelectValue placeholder="نوع الوقود" /></SelectTrigger>
      <SelectContent>
        <SelectItem value="diesel">ديزل</SelectItem>
        <SelectItem value="gas">بنزين</SelectItem>
        <SelectItem value="electric">كهرباء</SelectItem>
      </SelectContent>
    </Select>

    <Button className="lg:col-span-6">بحث متقدم ومحركات حديثة</Button>
  </section>

  {/* Main Sections */}
  <section className="mb-12 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-5">
    {["السيارات", "القصّات", "المحركات", "قطع التبديل"].map((section) => (
      <Card key={section} className="rounded-2xl shadow-sm">
        <CardContent className="p-6 text-center">
          <div className="mb-4 h-24 rounded-xl bg-gray-200" />
          <h2 className="text-xl font-semibold">{section}</h2>
          <p className="mt-2 text-sm text-gray-600">عرض وبيع دولي مع محركات بحث متطورة</p>
          <Button className="mt-4 w-full">دخول القسم</Button>
        </CardContent>
      </Card>
    ))}
  </section>

  {/* Listings */}
  <section className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
    {[1, 2, 3, 4, 5, 6].map((item) => (
      <Card key={item} className="rounded-2xl shadow-sm">
        <CardContent className="p-4">
          <div className="mb-3 h-40 rounded-xl bg-gray-200" />
          <h2 className="text-lg font-semibold">إعلان دولي رقم {item}</h2>
          <p className="text-sm text-gray-600">جاهز للتصدير • فحص • شحن متوفر</p>
          <div className="mt-3 flex gap-2">
            <Button className="flex-1">التفاصيل</Button>
            <Button variant="outline" className="flex items-center gap-1"><Phone className="h-4 w-4" /> اتصال</Button>
            <Button variant="outline" className="flex items-center gap-1"><MessageCircle className="h-4 w-4" /> واتساب</Button>
          </div>
        </CardContent>
      </Card>
    ))}
  </section>

  {/* Footer */}
  <footer className="mt-12 border-t pt-6 text-center text-sm text-gray-500">
    © {new Date().getFullYear()} AIB-SY GLOBAL – سوق السيارات وقطعها الدولي
  </footer>
</div>

); }
