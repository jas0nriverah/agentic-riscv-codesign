; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x11 (bvshl independent_opaque_0 (bvand (_ bv6 32) (_ bv31 32)))))
(let ((?x40 (bvadd independent_opaque_0 ?x11)))
(let ((?x29 (bvadd ?x11 independent_opaque_0)))
(and (distinct ?x29 ?x40) true)))))
(check-sat)
