; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x38 (bvshl independent_opaque_0 (bvand (_ bv3 32) (_ bv31 32)))))
(let ((?x60 (bvadd independent_opaque_0 ?x38)))
(let ((?x52 (bvadd ?x38 independent_opaque_0)))
(and (distinct ?x52 ?x60) true)))))
(check-sat)
