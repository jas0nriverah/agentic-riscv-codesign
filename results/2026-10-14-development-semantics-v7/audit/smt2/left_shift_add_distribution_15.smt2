(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x183 (bvshl y (_ bv15 32))))
(let ((?x179 (bvshl x (_ bv15 32))))
(let ((?x184 (bvadd ?x179 ?x183)))
(let ((?x19 (bvadd x y)))
(let ((?x182 (bvshl ?x19 (_ bv15 32))))
(and (distinct ?x182 ?x184) true)))))))
(check-sat)
