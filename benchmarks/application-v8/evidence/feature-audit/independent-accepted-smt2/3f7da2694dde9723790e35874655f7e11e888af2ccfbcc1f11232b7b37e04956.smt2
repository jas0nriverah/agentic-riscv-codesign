; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x61 (bvadd (bvsub (_ bv0 32) independent_opaque_1) (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32))))))
(let ((?x557 (bvadd independent_opaque_0 (bvsub (_ bv0 32) (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32)))))))
(let ((?x126 (bvadd ?x557 ?x61)))
(let ((?x13 (bvsub independent_opaque_1 independent_opaque_0)))
(let ((?x41 (bvadd (bvshl ?x13 (bvand (_ bv1 32) (_ bv31 32))) ?x13)))
(and (distinct ?x41 ?x126) true)))))))
(check-sat)
