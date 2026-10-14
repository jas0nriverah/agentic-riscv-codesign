(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x326 (bvshl y (_ bv31 32))))
(let ((?x322 (bvshl x (_ bv31 32))))
(let ((?x327 (bvadd ?x322 ?x326)))
(let ((?x19 (bvadd x y)))
(let ((?x325 (bvshl ?x19 (_ bv31 32))))
(and (distinct ?x325 ?x327) true)))))))
(check-sat)
