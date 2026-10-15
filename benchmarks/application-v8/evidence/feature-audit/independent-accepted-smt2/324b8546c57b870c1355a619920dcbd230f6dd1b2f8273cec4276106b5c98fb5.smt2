; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x66 (bvadd independent_opaque_1 (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32)))))))
(let ((?x48 (bvadd (bvsub (_ bv0 32) independent_opaque_0) (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32))))))
(let ((?x47 (bvadd ?x48 ?x66)))
(let ((?x43 (bvsub independent_opaque_0 independent_opaque_1)))
(let ((?x45 (bvadd (bvshl ?x43 (bvand (_ bv1 32) (_ bv31 32))) ?x43)))
(and (distinct ?x45 ?x47) true)))))))
(check-sat)
