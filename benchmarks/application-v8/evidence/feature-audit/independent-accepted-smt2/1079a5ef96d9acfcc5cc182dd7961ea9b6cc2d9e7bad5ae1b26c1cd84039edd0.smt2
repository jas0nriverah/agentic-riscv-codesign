; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x64 (bvadd independent_opaque_0 (bvadd (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32))) (_ bv4294967184 32)))))
(let ((?x45 (bvadd independent_opaque_0 (bvshl (bvadd independent_opaque_1 (_ bv4294967268 32)) (bvand (_ bv2 32) (_ bv31 32))))))
(and (distinct ?x45 ?x64) true))))
(check-sat)
